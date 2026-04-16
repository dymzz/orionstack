from fastapi import APIRouter

from app.config.settings import settings
from app.runtime.trace import new_trace_id
from app.schemas.request import ChatAskRequest, ChatFeedbackRequest
from app.schemas.response import ChatAskResponse, ChatFeedbackResponse, DebugInfo
from app.services.chat_service import ChatService
from app.storage.repositories.feedback_repo import FeedbackRepository

router = APIRouter(prefix="/api/chat", tags=["chat"])
service = ChatService()
feedback_repository = FeedbackRepository()


@router.post("/ask", response_model=ChatAskResponse)
def ask_chat(payload: ChatAskRequest) -> ChatAskResponse:
    trace_id = new_trace_id()
    debug_enabled = payload.debug and settings.debug_response_enabled
    try:
        return service.ask(payload, trace_id=trace_id, debug_enabled=debug_enabled)
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

        return ChatAskResponse(
            response_status="system_error",
            trace_id=trace_id,
            answer="系统暂时不可用，请稍后重试。",
            citations=[],
            debug_info=debug_info,
        )


@router.post("/feedback", response_model=ChatFeedbackResponse)
def submit_feedback(payload: ChatFeedbackRequest) -> ChatFeedbackResponse:
    feedback_repository.save(
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
    return ChatFeedbackResponse(status="recorded")
