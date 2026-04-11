from sqlalchemy import select

from app.core.database import session_scope
from app.models.entities import SessionORM


class SessionRepository:
    def save(self, session: SessionORM) -> SessionORM:
        with session_scope() as db:
            db.add(session)
            db.flush()
            db.refresh(session)
        return session

    def list(self) -> list[SessionORM]:
        with session_scope() as db:
            stmt = select(SessionORM).order_by(SessionORM.created_at.desc())
            return list(db.scalars(stmt))

    def get(self, session_id: str) -> SessionORM | None:
        with session_scope() as db:
            return db.get(SessionORM, session_id)
