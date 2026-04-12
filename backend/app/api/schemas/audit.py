from datetime import datetime
from typing import Any

from pydantic import BaseModel


class AuditLogItemResponse(BaseModel):
    id: int
    owner_user_id: str
    trace_id: str
    event_type: str
    payload: dict[str, Any]
    created_at: datetime


class AuditLogListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    has_more: bool
    items: list[AuditLogItemResponse]
