from datetime import datetime
import json
from typing import Any, Literal

from pydantic import Field, field_validator

from app.knowledge.contracts import CoreContract, EntityRef, content_hash


class ActionContext(CoreContract):
    request_id: str = Field(min_length=1, max_length=200)


class ActionRequest(CoreContract):
    action: str = Field(min_length=1, max_length=100, pattern=r"^[a-z][a-z0-9_]*$")
    entity: EntityRef
    parameters: dict[str, Any]
    context: ActionContext

    def payload_fingerprint(self) -> str:
        return content_hash(json.dumps(
            self.model_dump(mode="json"), sort_keys=True,
            separators=(",", ":"), ensure_ascii=False, allow_nan=False,
        ))


class ActionReceipt(CoreContract):
    action_id: str
    request_id: str
    status: Literal["accepted", "duplicate"]


class EventSource(CoreContract):
    namespace: str = Field(min_length=1)
    record_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    source_locator: str | None = None
    content_hash: str | None = None


class EventRequest(CoreContract):
    schema_version: Literal["1"] = "1"
    event_id: str = Field(min_length=1, max_length=200)
    event_type: str = Field(min_length=1)
    occurred_at: datetime
    source: EventSource
    payload: dict[str, Any]
    request_id: str | None = None
    subject: EntityRef | None = None

    @field_validator("occurred_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Event time must include a timezone")
        return value


class EventReceipt(CoreContract):
    event_id: str
    status: Literal["accepted", "duplicate"]
    processing_id: str | None = None
