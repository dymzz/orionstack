from pydantic import BaseModel, Field


class AskQuestionRequest(BaseModel):
    session_id: str
    question: str = Field(..., min_length=1)
    document_ids: list[str] = []
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
