from datetime import datetime
from pydantic import BaseModel, Field


class CreateSessionRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    scene: str = Field(default="knowledge_assistant")


class SessionResponse(BaseModel):
    session_id: str
    title: str
    scene: str
    created_at: datetime


class SessionListResponse(BaseModel):
    items: list[SessionResponse]
