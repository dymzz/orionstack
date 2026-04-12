from sqlalchemy import func, select

from app.core.database import session_scope
from app.models.entities import QAHistoryORM


class QAHistoryRepository:
    def append(self, item: QAHistoryORM) -> QAHistoryORM:
        with session_scope() as db:
            db.add(item)
            db.flush()
            db.refresh(item)
        return item

    def count_by_session(self, session_id: str, *, owner_user_id: str | None = None) -> int:
        with session_scope() as db:
            stmt = select(func.count(QAHistoryORM.id)).where(QAHistoryORM.session_id == session_id)
            if owner_user_id:
                stmt = stmt.where(QAHistoryORM.owner_user_id == owner_user_id)
            return int(db.scalar(stmt) or 0)

    def list_by_session(
        self,
        session_id: str,
        *,
        limit: int = 20,
        offset: int = 0,
        order: str = "desc",
        owner_user_id: str | None = None,
    ) -> list[QAHistoryORM]:
        with session_scope() as db:
            if order == "asc":
                ordering = [QAHistoryORM.created_at.asc(), QAHistoryORM.id.asc()]
            else:
                ordering = [QAHistoryORM.created_at.desc(), QAHistoryORM.id.desc()]

            stmt = select(QAHistoryORM).where(QAHistoryORM.session_id == session_id)
            if owner_user_id:
                stmt = stmt.where(QAHistoryORM.owner_user_id == owner_user_id)
            stmt = stmt.order_by(*ordering)
            if offset > 0:
                stmt = stmt.offset(offset)
            stmt = stmt.limit(limit)
            return list(db.scalars(stmt))
