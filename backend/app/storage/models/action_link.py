from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ActionLink:
    action_link_id: str
    tenant_id: str
    source_record_id: str
    label: str
    system_type: str
    url: str
    resource_type: str
    access_scope: str
    status: str
    published_at: str
    fresh_until: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_link_id": self.action_link_id,
            "tenant_id": self.tenant_id,
            "source_record_id": self.source_record_id,
            "label": self.label,
            "system_type": self.system_type,
            "url": self.url,
            "resource_type": self.resource_type,
            "access_scope": self.access_scope,
            "status": self.status,
            "published_at": self.published_at,
            "fresh_until": self.fresh_until,
        }
