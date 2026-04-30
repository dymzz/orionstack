from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ExtractionTask:
    extraction_task_id: str
    tenant_id: str
    source_record_id: str
    source_system: str
    external_id: str
    reason: str
    status: str
    created_at: str
    import_batch_id: str | None = None
    supersedes_source_record_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "extraction_task_id": self.extraction_task_id,
            "tenant_id": self.tenant_id,
            "source_record_id": self.source_record_id,
            "source_system": self.source_system,
            "external_id": self.external_id,
            "reason": self.reason,
            "status": self.status,
            "created_at": self.created_at,
            "import_batch_id": self.import_batch_id,
            "supersedes_source_record_id": self.supersedes_source_record_id,
        }
