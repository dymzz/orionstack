from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CleanupTask:
    cleanup_task_id: str
    tenant_id: str
    source_record_id: str
    source_system: str
    external_id: str
    reason: str
    status: str
    source_status: str
    created_at: str
    import_batch_id: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    error_summary: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "cleanup_task_id": self.cleanup_task_id,
            "tenant_id": self.tenant_id,
            "source_record_id": self.source_record_id,
            "source_system": self.source_system,
            "external_id": self.external_id,
            "reason": self.reason,
            "status": self.status,
            "source_status": self.source_status,
            "created_at": self.created_at,
            "import_batch_id": self.import_batch_id,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "error_summary": self.error_summary,
        }
