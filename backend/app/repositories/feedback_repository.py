from app.core.database import session_scope
from app.models.entities import FeedbackORM


class FeedbackRepository:
    def save(self, feedback: FeedbackORM) -> FeedbackORM:
        with session_scope() as db:
            db.add(feedback)
            db.flush()
            db.refresh(feedback)
        return feedback
