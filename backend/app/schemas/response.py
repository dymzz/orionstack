from typing import Literal

from pydantic import BaseModel


class CitationItem(BaseModel):
    citation_id: str
    source_label: str
    source_locator: str
    snippet: str


class DebugInfo(BaseModel):
    normalized_query: str
    route_result: str
    router_used: str
    retrieved_chunks: list[str]
    route_confidence: float | None = None
    retrieval_score: float | None = None
    fallback_reason: str | None = None


class ChatAskResponse(BaseModel):
    response_status: Literal["ok", "refused", "fallback", "system_error"]
    trace_id: str
    answer: str
    citations: list[CitationItem]
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
