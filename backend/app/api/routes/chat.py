from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.observability.retrieval_trace import RetrievalTraceRepository
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
from app.testing.hard_cases_repo import HardCasesRepository
from app.storage.repositories.chat_record_repo import ChatRecordRepository
from app.storage.repositories.feedback_repo import FeedbackRepository

router = APIRouter(prefix="/api/chat", tags=["chat"])
service = ChatService()
feedback_repository = FeedbackRepository(max_count=settings.feedback_record_max_count)
chat_record_repository = ChatRecordRepository(max_count=settings.chat_record_max_count)
retrieval_trace_repository = RetrievalTraceRepository()
hard_cases_repository = HardCasesRepository()


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
    retrieval_trace = retrieval_trace_repository.save(
        _build_retrieval_trace_record(payload, response)
    )
    _record_hard_case_from_response(retrieval_trace)
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
    _record_hard_case_from_feedback(payload)
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


@router.get("/traces/{trace_id}")
def get_retrieval_trace(trace_id: str) -> dict[str, Any]:
    _ensure_record_view_enabled()
    trace = retrieval_trace_repository.get_by_trace_id(trace_id)
    if trace is None:
        raise HTTPException(status_code=404, detail="Trace not found")
    return trace


@router.get("/hard-cases")
def list_hard_cases(
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, list[dict[str, Any]]]:
    _ensure_record_view_enabled()
    return {"items": hard_cases_repository.list_recent(limit)}


def _resolve_retrieved_chunk_ids(response: ChatAskResponse) -> list[str]:
    if response.debug_info is not None and response.debug_info.retrieved_chunks:
        return response.debug_info.retrieved_chunks
    return [citation.citation_id for citation in response.citations]


def _build_retrieval_trace_record(
    payload: ChatAskRequest,
    response: ChatAskResponse,
) -> dict[str, Any]:
    debug_info = response.debug_info
    return {
        "trace_id": response.trace_id,
        "raw_query": payload.raw_query,
        "normalized_query": payload.raw_query.strip()
        if debug_info is None
        else debug_info.normalized_query,
        "intent": None if debug_info is None else debug_info.route_result,
        "router_used": None if debug_info is None else debug_info.router_used,
        "retrieval_score": None
        if debug_info is None
        else getattr(debug_info, "retrieval_score", None),
        "fusion_score": None
        if debug_info is None
        else getattr(debug_info, "fusion_score", None),
        "domain_hint": None if debug_info is None else getattr(debug_info, "domain_hint", None),
        "semantic_expansions": None
        if debug_info is None
        else getattr(debug_info, "semantic_expansions", None),
        "lexical_terms": None
        if debug_info is None
        else getattr(debug_info, "lexical_terms", None),
        "retrieval_mode": None
        if debug_info is None
        else getattr(debug_info, "retrieval_mode", None),
        "lexical_topk": None
        if debug_info is None
        else [
            item.model_dump()
            for item in getattr(debug_info, "lexical_topk", []) or []
        ],
        "vector_topk": None
        if debug_info is None
        else [
            item.model_dump()
            for item in getattr(debug_info, "vector_topk", []) or []
        ],
        "rrf_topk": None
        if debug_info is None
        else [item.model_dump() for item in getattr(debug_info, "rrf_topk", []) or []],
        "rerank_accept": None
        if debug_info is None
        else getattr(debug_info, "rerank_accept", None),
        "rerank_score": None
        if debug_info is None
        else getattr(debug_info, "rerank_score", None),
        "evidence_confidence": None
        if debug_info is None
        else getattr(debug_info, "evidence_confidence", None),
        "evidence_span_count": None
        if debug_info is None
        else getattr(debug_info, "evidence_span_count", None),
        "reject_reason": None
        if debug_info is None
        else getattr(debug_info, "reject_reason", None),
        "source_record_id": None
        if debug_info is None
        else getattr(debug_info, "source_record_id", None),
        "import_batch_id": None
        if debug_info is None
        else getattr(debug_info, "import_batch_id", None),
        "unit_version": None
        if debug_info is None
        else getattr(debug_info, "unit_version", None),
        "dynamic_query_key": None
        if debug_info is None
        else getattr(debug_info, "dynamic_query_key", None),
        "freshness_status": None
        if debug_info is None
        else getattr(debug_info, "freshness_status", None),
        "filters": {
            "document_ids": payload.document_ids,
        },
        "retrieved_chunks": _resolve_retrieved_chunk_ids(response),
        "citations": [
            {
                "citation_id": citation.citation_id,
                "source_label": citation.source_label,
                "source_locator": citation.source_locator,
                "snippet": citation.snippet,
            }
            for citation in response.citations
        ],
        "fallback_reason": None if debug_info is None else debug_info.fallback_reason,
        "final_status": response.response_status,
    }


def _record_hard_case_from_response(retrieval_trace: dict[str, Any]) -> None:
    fallback_reason = retrieval_trace.get("fallback_reason")
    if fallback_reason is None:
        return
    if retrieval_trace.get("final_status") != "fallback":
        return
    hard_cases_repository.upsert(_build_hard_case_item(retrieval_trace))


def _record_hard_case_from_feedback(payload: ChatFeedbackRequest) -> None:
    if payload.feedback_label != "down":
        return

    retrieval_trace = retrieval_trace_repository.get_by_trace_id(payload.trace_id)
    if retrieval_trace is None:
        return

    hard_cases_repository.upsert(
        _build_hard_case_item(
            retrieval_trace,
            user_feedback=payload.feedback_label,
        )
    )


def _build_hard_case_item(
    retrieval_trace: dict[str, Any],
    *,
    user_feedback: str | None = None,
    issue_category: str | None = None,
) -> dict[str, Any]:
    fallback_reason = retrieval_trace.get("fallback_reason")
    if issue_category is None:
        issue_category = _infer_issue_category(retrieval_trace)
    return {
        "trace_id": retrieval_trace.get("trace_id", ""),
        "raw_query": retrieval_trace.get("raw_query", ""),
        "normalized_query": retrieval_trace.get("normalized_query", ""),
        "router_used": retrieval_trace.get("router_used"),
        "domain_hint": retrieval_trace.get("domain_hint"),
        "fallback_reason": fallback_reason,
        "top_candidates": retrieval_trace.get("citations", []),
        "evidence_spans": [
            {"text": citation.get("snippet", "")}
            for citation in retrieval_trace.get("citations", [])
            if citation.get("snippet")
        ],
        "user_feedback": user_feedback,
        "issue_category": issue_category,
        "source_record_id": retrieval_trace.get("source_record_id"),
        "import_batch_id": retrieval_trace.get("import_batch_id"),
        "unit_version": retrieval_trace.get("unit_version"),
        "dynamic_query_key": retrieval_trace.get("dynamic_query_key"),
    }


def _infer_issue_category(retrieval_trace: dict[str, Any]) -> str:
    fallback_reason = retrieval_trace.get("fallback_reason")
    reject_reason = str(retrieval_trace.get("reject_reason") or "")
    if fallback_reason == "evidence_below_threshold":
        return "evidence_weak"
    if fallback_reason == "no_evidence":
        return "retrieval_miss"
    if fallback_reason == "conflict_requires_clarification":
        return "retrieval_ambiguous"
    if fallback_reason in ("retrieval_no_hit", "retrieval_score_below_threshold"):
        return "retrieval_miss"
    if fallback_reason in ("route_not_confident_enough",):
        return "routing_mismatch"
    if fallback_reason == "stale_knowledge":
        return "freshness_stale"
    if "evidence_below_threshold" in reject_reason:
        return "evidence_weak"
    if retrieval_trace.get("source_record_id"):
        return "extraction_drift"
    return "unknown"


def _ensure_record_view_enabled() -> None:
    if not settings.chat_record_view_enabled:
        raise HTTPException(status_code=404, detail="Not Found")
