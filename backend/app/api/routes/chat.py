from fastapi import APIRouter, HTTPException, Query

from app.config.settings import settings
from app.runtime.trace import new_trace_id
from app.schemas.request import ChatAskRequest, ChatFeedbackRequest
from app.schemas.response import (
    ChatAskResponse,
    ChatFeedbackResponse,
    ChatRecordItem,
    ChatRecordListResponse,
    DebugInfo,
    FeedbackRecordItem,
    FeedbackRecordListResponse,
)
from app.services.chat_service import ChatService
from app.storage.repositories.chat_record_repo import ChatRecordRepository
from app.storage.repositories.feedback_repo import FeedbackRepository

router = APIRouter(prefix="/api/chat", tags=["chat"])
service = ChatService()
feedback_repository = FeedbackRepository(max_count=settings.feedback_record_max_count)
chat_record_repository = ChatRecordRepository(max_count=settings.chat_record_max_count)


@router.post("/ask", response_model=ChatAskResponse)
def ask_chat(payload: ChatAskRequest) -> ChatAskResponse:
    trace_id = new_trace_id()
    debug_enabled = payload.debug and settings.debug_response_enabled
    try:
        response = service.ask(payload, trace_id=trace_id, debug_enabled=debug_enabled)
    except Exception as error:  # pragma: no cover - minimal demo fallback
        debug_info = None
        if debug_enabled:
            debug_info = DebugInfo(
                normalized_query=payload.raw_query.strip(),
                route_result="system_error",
                router_used="rule_parser",
                retrieved_chunks=[],
                route_confidence=0.0,
                fallback_reason=error.__class__.__name__,
            )

        response = ChatAskResponse(
            response_status="system_error",
            trace_id=trace_id,
            answer="系统暂时不可用，请稍后重试。",
            citations=[],
            debug_info=debug_info,
        )

    chat_record_repository.save(
        {
            "trace_id": response.trace_id,
            "raw_query": payload.raw_query,
            "document_ids": payload.document_ids,
            "response_status": response.response_status,
            "retrieved_chunk_ids": _resolve_retrieved_chunk_ids(response),
        }
    )
    return response


@router.post("/feedback", response_model=ChatFeedbackResponse)
def submit_feedback(payload: ChatFeedbackRequest) -> ChatFeedbackResponse:
    feedback_record = feedback_repository.save(
        {
            "trace_id": payload.trace_id,
            "raw_query": payload.raw_query,
            "retrieved_chunk_ids": payload.retrieved_chunk_ids,
            "answer_text": payload.answer_text,
            "feedback_label": payload.feedback_label,
            "token_input": 0,
            "token_output": 0,
            "total_latency_ms": 0,
            "response_status": payload.response_status,
            "normalized_query": payload.normalized_query,
            "router_used": payload.router_used,
            "route_result": payload.route_result,
            "fallback_reason": payload.fallback_reason,
        }
    )
    chat_record_repository.attach_feedback(
        trace_id=payload.trace_id,
        feedback_label=payload.feedback_label,
        feedback_created_at=str(feedback_record["created_at"]),
    )
    return ChatFeedbackResponse(status="recorded")


@router.get("/records", response_model=ChatRecordListResponse)
def list_chat_records(
    limit: int = Query(default=50, ge=1, le=200),
) -> ChatRecordListResponse:
    _ensure_record_view_enabled()
    items = [
        ChatRecordItem(
            trace_id=str(record.get("trace_id", "")),
            raw_query=str(record.get("raw_query", "")),
            response_status=str(record.get("response_status", "")),
            retrieved_chunk_ids=list(record.get("retrieved_chunk_ids", [])),
            created_at=str(record.get("created_at", "")),
            feedback_label=record.get("feedback_label"),
        )
        for record in chat_record_repository.list_recent(limit)
    ]
    return ChatRecordListResponse(items=items)


@router.get("/feedback", response_model=FeedbackRecordListResponse)
def list_feedback_records(
    limit: int = Query(default=50, ge=1, le=200),
) -> FeedbackRecordListResponse:
    _ensure_record_view_enabled()
    items = [
        FeedbackRecordItem(
            trace_id=str(record.get("trace_id", "")),
            raw_query=str(record.get("raw_query", "")),
            feedback_label=str(record.get("feedback_label", "")),
            response_status=str(record.get("response_status", "")),
            created_at=str(record.get("created_at", "")),
        )
        for record in feedback_repository.list_recent(limit)
    ]
    return FeedbackRecordListResponse(items=items)


def _resolve_retrieved_chunk_ids(response: ChatAskResponse) -> list[str]:
    if response.debug_info is not None and response.debug_info.retrieved_chunks:
        return response.debug_info.retrieved_chunks
    return [citation.citation_id for citation in response.citations]


def _ensure_record_view_enabled() -> None:
    if not settings.chat_record_view_enabled:
        raise HTTPException(status_code=404, detail="Not Found")
