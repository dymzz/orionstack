from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ImportBatch:
    import_batch_id: str
    tenant_id: str
    source_system: str
    mode: str
    started_at: str
    status: str
    finished_at: str | None = None
    record_count: int = 0
    error_summary: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "import_batch_id": self.import_batch_id,
            "tenant_id": self.tenant_id,
            "source_system": self.source_system,
            "mode": self.mode,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "status": self.status,
            "record_count": self.record_count,
            "error_summary": self.error_summary,
        }
