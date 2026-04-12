from typing import Any, Dict, List, Optional, TypedDict


class KnowledgeAssistantState(TypedDict, total=False):
    trace_id: str
    user_id: str
    session_id: str
    question: str
    document_ids: List[str]
    top_k: int
    use_rerank: bool
    retrieved_chunks: List[Dict[str, Any]]
    citations: List[Dict[str, Any]]
    answer: str
    retrieval_confidence: float
    should_refuse: bool
    refusal_reason: Optional[str]
    error: Optional[str]
    need_human_review: bool
