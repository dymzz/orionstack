from datetime import datetime, timezone
import hashlib
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CoreContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class EntityRef(CoreContract):
    type: str = Field(min_length=1)
    id: str = Field(min_length=1)


class QueryContext(CoreContract):
    query: str = Field(min_length=1, max_length=4000)
    entities: tuple[EntityRef, ...] = ()
    document_ids: tuple[str, ...] = ()

    @field_validator("query")
    @classmethod
    def preserve_query(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Query cannot be blank")
        # Raw facts bind the exact text embedded, including user-provided whitespace.
        return value


class AccessContext(CoreContract):
    """Internal principal, built from authentication rather than request JSON."""
    tenant_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    roles: tuple[str, ...] = ()
    allowed_scopes: tuple[str, ...] = ("internal",)


class SourceRef(CoreContract):
    source_id: str = Field(min_length=1)
    source_version: str = Field(min_length=1)
    source_locator: str = Field(min_length=1)
    document_id: str | None = None
    document_version: str | None = None
    chunk_id: str | None = None
    record_id: str | None = None
    content_hash: str | None = None
    page: int | None = Field(default=None, ge=1)
    section: str | None = None


class EvidenceCandidate(CoreContract):
    evidence_id: str = Field(min_length=1)
    evidence_kind: Literal["structured_record", "document_chunk"]
    tenant_id: str = Field(min_length=1)
    access_scope: str = Field(min_length=1)
    source: SourceRef
    text: str = Field(min_length=1)
    typed_values: dict[str, Any] = Field(default_factory=dict)
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    retrieval_method: str = Field(min_length=1)
    retrieval_score: float | None = Field(default=None, allow_inf_nan=False)


def content_hash(data: bytes | str) -> str:
    """Full SHA-256; preserve text exactly so the source fingerprint is reproducible."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()
