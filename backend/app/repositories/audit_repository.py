from sqlalchemy import func, select

from app.core.database import session_scope
from app.models.entities import AuditLogORM


class AuditRepository:
    def append(self, item: AuditLogORM) -> AuditLogORM:
        with session_scope() as db:
            db.add(item)
            db.flush()
            db.refresh(item)
        return item

    def count_by_owner(self, owner_user_id: str) -> int:
        with session_scope() as db:
            stmt = select(func.count(AuditLogORM.id)).where(AuditLogORM.owner_user_id == owner_user_id)
            return int(db.scalar(stmt) or 0)

    def list_by_owner(self, owner_user_id: str, *, limit: int = 50, offset: int = 0) -> list[AuditLogORM]:
        with session_scope() as db:
            stmt = (
                select(AuditLogORM)
                .where(AuditLogORM.owner_user_id == owner_user_id)
                .order_by(AuditLogORM.created_at.desc(), AuditLogORM.id.desc())
                .offset(max(offset, 0))
                .limit(max(1, min(limit, 200)))
            )
            return list(db.scalars(stmt))
