from app.core.database import session_scope
from app.models.entities import FeedbackORM


class FeedbackRepository:
    def save(self, feedback: FeedbackORM) -> FeedbackORM:
        with session_scope() as db:
            db.add(feedback)
            db.flush()
            db.refresh(feedback)
        return feedback

    def count_by_owner(self, owner_user_id: str) -> int:
        from sqlalchemy import func, select

        with session_scope() as db:
            stmt = select(func.count(FeedbackORM.feedback_id)).where(FeedbackORM.owner_user_id == owner_user_id)
            return int(db.scalar(stmt) or 0)
