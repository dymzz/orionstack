from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ExtractionCandidate:
    candidate_id: str
    tenant_id: str
    source_record_id: str
    candidate_type: str
    payload_json: str
    extractor_model: str
    prompt_version: str
    source_span: str
    source_span_hash: str
    review_status: str
    created_at: str
    reviewed_by: str | None = None
    reviewed_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "tenant_id": self.tenant_id,
            "source_record_id": self.source_record_id,
            "candidate_type": self.candidate_type,
            "payload_json": self.payload_json,
            "extractor_model": self.extractor_model,
            "prompt_version": self.prompt_version,
            "source_span": self.source_span,
            "source_span_hash": self.source_span_hash,
            "review_status": self.review_status,
            "reviewed_by": self.reviewed_by,
            "reviewed_at": self.reviewed_at,
            "created_at": self.created_at,
        }
