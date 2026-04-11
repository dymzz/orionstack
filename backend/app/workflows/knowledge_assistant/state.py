from typing import Any, Dict, List, Optional, TypedDict


class KnowledgeAssistantState(TypedDict, total=False):
    trace_id: str
    user_id: str
    session_id: str
    question: str
    document_ids: List[str]
    retrieved_chunks: List[Dict[str, Any]]
    citations: List[Dict[str, Any]]
    answer: str
    error: Optional[str]
    need_human_review: bool
