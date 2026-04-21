from typing import Literal

from pydantic import BaseModel


class CitationItem(BaseModel):
    citation_id: str
    source_label: str
    source_locator: str
    snippet: str


class ClarificationOption(BaseModel):
    option_id: str
    label: str


class ClarificationInfo(BaseModel):
    clarification_required: bool
    question: str
    options: list[ClarificationOption]
    conflict_reason: str | None = None


class RetrievalCandidateSummary(BaseModel):
    unit_id: str
    score: float
    source_kind: str
    lexical_dominance_applied: bool | None = None
    vector_dominance_applied: bool | None = None


class DebugInfo(BaseModel):
    normalized_query: str
    route_result: str
    router_used: str
    retrieved_chunks: list[str]
    route_confidence: float | None = None
    retrieval_score: float | None = None
    fusion_score: float | None = None
    fallback_reason: str | None = None
    domain_hint: str | None = None
    lexical_terms: list[str] | None = None
    semantic_expansions: list[str] | None = None
    planner_confidence: float | None = None
    retrieval_mode: Literal[
        "lexical_only", "hybrid", "hybrid_rerank", "clarification"
    ] | None = None
    lexical_topk: list[RetrievalCandidateSummary] | None = None
    vector_topk: list[RetrievalCandidateSummary] | None = None
    rrf_topk: list[RetrievalCandidateSummary] | None = None
    rerank_accept: bool | None = None
    rerank_score: float | None = None
    evidence_confidence: float | None = None
    evidence_span_count: int | None = None
    reject_reason: str | None = None


class ChatAskResponse(BaseModel):
    response_status: Literal["ok", "refused", "fallback", "system_error"]
    trace_id: str
    answer: str
    citations: list[CitationItem]
    clarification: ClarificationInfo | None = None
    debug_info: DebugInfo | None = None


class ChatFeedbackResponse(BaseModel):
    status: Literal["recorded"]


class ChatRecordItem(BaseModel):
    trace_id: str
    raw_query: str
    response_status: str
    retrieved_chunk_ids: list[str]
    created_at: str
    feedback_label: str | None = None


class ChatRecordListResponse(BaseModel):
    items: list[ChatRecordItem]


class FeedbackRecordItem(BaseModel):
    trace_id: str
    raw_query: str
    feedback_label: str
    response_status: str
    created_at: str


class FeedbackRecordListResponse(BaseModel):
    items: list[FeedbackRecordItem]
