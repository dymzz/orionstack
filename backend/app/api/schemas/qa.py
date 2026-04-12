from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class AskQuestionRequest(BaseModel):
    session_id: str
    question: str = Field(..., min_length=1)
    document_ids: list[str] = Field(default_factory=list)
    top_k: int = 5
    use_rerank: bool = True


class CitationItem(BaseModel):
    document_id: str
    document_name: str
    chunk_id: str
    snippet: str
    score: float


class AskQuestionResponse(BaseModel):
    answer: str
    citations: list[CitationItem]
    trace_id: str
    latency_ms: int
    retrieval_confidence: Optional[float] = None
    refusal_reason: Optional[str] = None
    need_human_review: bool = False
    answer_provider: Optional[str] = None


class QAHistoryItemResponse(BaseModel):
    trace_id: str
    question: str
    answer: str
    latency_ms: int
    retrieval_confidence: Optional[float] = None
    refusal_reason: Optional[str] = None
    need_human_review: bool = False
    answer_provider: Optional[str] = None
    created_at: datetime
    citations: list[CitationItem]


class QAHistoryResponse(BaseModel):
    session_id: str
    total: int = 0
    limit: int = 20
    offset: int = 0
    order: str = "desc"
    has_more: bool = False
    items: list[QAHistoryItemResponse]
