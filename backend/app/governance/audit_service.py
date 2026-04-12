from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.api.schemas.audit import AuditLogItemResponse, AuditLogListResponse
from app.models.entities import AuditLogORM
from app.repositories.audit_repository import AuditRepository


class AuditService:
    def __init__(self) -> None:
        self.repository = AuditRepository()

    def log(
        self,
        *,
        owner_user_id: str,
        event_type: str,
        trace_id: str = "",
        payload: dict[str, Any] | None = None,
    ) -> None:
        self.repository.append(
            AuditLogORM(
                owner_user_id=owner_user_id,
                event_type=event_type,
                trace_id=trace_id,
                payload_json=payload or {},
                created_at=datetime.now(UTC),
            )
        )

    def list_logs(self, *, owner_user_id: str, limit: int = 50, offset: int = 0) -> AuditLogListResponse:
        safe_limit = max(1, min(limit, 200))
        safe_offset = max(0, offset)
        total = self.repository.count_by_owner(owner_user_id)
        rows = self.repository.list_by_owner(owner_user_id, limit=safe_limit, offset=safe_offset)
        items = [
            AuditLogItemResponse(
                id=row.id,
                owner_user_id=row.owner_user_id,
                trace_id=row.trace_id,
                event_type=row.event_type,
                payload=row.payload_json or {},
                created_at=row.created_at,
            )
            for row in rows
        ]
        return AuditLogListResponse(
            total=total,
            limit=safe_limit,
            offset=safe_offset,
            has_more=(safe_offset + len(items)) < total,
            items=items,
        )
