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

    def list(self, *, owner_user_id: str | None = None) -> list[SessionORM]:
        with session_scope() as db:
            stmt = select(SessionORM).order_by(SessionORM.created_at.desc())
            if owner_user_id:
                stmt = stmt.where(SessionORM.owner_user_id == owner_user_id)
            return list(db.scalars(stmt))

    def get(self, session_id: str, *, owner_user_id: str | None = None) -> SessionORM | None:
        with session_scope() as db:
            stmt = select(SessionORM).where(SessionORM.session_id == session_id)
            if owner_user_id:
                stmt = stmt.where(SessionORM.owner_user_id == owner_user_id)
            return db.scalar(stmt)
