from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class SourceRecord:
    source_record_id: str
    tenant_id: str
    source_system: str
    source_object_type: str
    external_id: str
    source_locator: str
    title: str
    raw_content: str
    content_hash: str
    source_updated_at: str
    export_batch_id: str
    access_scope: str
    status: str
    synced_at: str
    import_batch_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_record_id": self.source_record_id,
            "tenant_id": self.tenant_id,
            "source_system": self.source_system,
            "source_object_type": self.source_object_type,
            "external_id": self.external_id,
            "source_locator": self.source_locator,
            "title": self.title,
            "raw_content": self.raw_content,
            "content_hash": self.content_hash,
            "source_updated_at": self.source_updated_at,
            "export_batch_id": self.export_batch_id,
            "import_batch_id": self.import_batch_id,
            "access_scope": self.access_scope,
            "status": self.status,
            "synced_at": self.synced_at,
        }

    @staticmethod
    def compute_content_hash(raw_content: str) -> str:
        return hashlib.sha256(raw_content.encode("utf-8")).hexdigest()[:16]
