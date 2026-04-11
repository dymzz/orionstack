from sqlalchemy import select

from app.core.database import session_scope
from app.models.entities import QAHistoryORM


class QAHistoryRepository:
    def append(self, item: QAHistoryORM) -> QAHistoryORM:
        with session_scope() as db:
            db.add(item)
            db.flush()
            db.refresh(item)
        return item

    def list_by_session(self, session_id: str) -> list[QAHistoryORM]:
        with session_scope() as db:
            stmt = (
                select(QAHistoryORM)
                .where(QAHistoryORM.session_id == session_id)
                .order_by(QAHistoryORM.created_at.asc(), QAHistoryORM.id.asc())
            )
            return list(db.scalars(stmt))
