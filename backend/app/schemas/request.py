from typing import Literal

from pydantic import BaseModel, Field


class ChatAskRequest(BaseModel):
    raw_query: str = Field(min_length=1, max_length=500)
    debug: bool = False


class ChatFeedbackRequest(BaseModel):
    trace_id: str = Field(min_length=1, max_length=64)
    raw_query: str = Field(min_length=1, max_length=500)
    answer_text: str = Field(min_length=1, max_length=4000)
    feedback_label: Literal["up", "down"]
    response_status: Literal["ok", "refused", "fallback", "system_error"]
    retrieved_chunk_ids: list[str] = Field(default_factory=list)
    normalized_query: str | None = Field(default=None, max_length=500)
    router_used: str | None = Field(default=None, max_length=100)
    route_result: str | None = Field(default=None, max_length=100)
    fallback_reason: str | None = Field(default=None, max_length=200)
