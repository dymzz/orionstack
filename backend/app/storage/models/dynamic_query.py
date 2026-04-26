from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DynamicQuery:
    dynamic_query_id: str
    tenant_id: str
    query_key: str
    resource_type: str
    action: str
    scope_type: str
    status: str
    description: str
    detect_patterns: tuple[str, ...] = ()
    source_record_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "dynamic_query_id": self.dynamic_query_id,
            "tenant_id": self.tenant_id,
            "query_key": self.query_key,
            "resource_type": self.resource_type,
            "action": self.action,
            "scope_type": self.scope_type,
            "status": self.status,
            "description": self.description,
            "detect_patterns": list(self.detect_patterns),
            "source_record_id": self.source_record_id,
        }
