from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from app.api.schemas.audit import AuditLogListResponse
from app.governance.audit_service import AuditService
from app.models.entities import FeedbackORM
from app.repositories.feedback_repository import FeedbackRepository
from app.repositories.session_repository import SessionRepository


class ActivityService:
    def __init__(self) -> None:
        self.audit_service = AuditService()
        self.feedback_repository = FeedbackRepository()
        self.session_repository = SessionRepository()

    def record_event(
        self,
        *,
        owner_user_id: str,
        event_type: str,
        trace_id: str = "",
        payload: dict | None = None,
    ) -> None:
        self.audit_service.log(
            owner_user_id=owner_user_id,
            event_type=event_type,
            trace_id=trace_id,
            payload=payload,
        )

    def list_audit_logs(self, *, owner_user_id: str, limit: int = 50, offset: int = 0) -> AuditLogListResponse:
        return self.audit_service.list_logs(owner_user_id=owner_user_id, limit=limit, offset=offset)

    def submit_feedback(
        self,
        *,
        owner_user_id: str,
        session_id: str,
        trace_id: str,
        rating: str,
        comment: str = "",
    ) -> str:
        session = self.session_repository.get(session_id, owner_user_id=owner_user_id)
        if session is None:
            raise ValueError("Session not found")

        feedback_id = str(uuid4())
        self.feedback_repository.save(
            FeedbackORM(
                feedback_id=feedback_id,
                owner_user_id=owner_user_id,
                session_id=session_id,
                trace_id=trace_id,
                rating=rating,
                comment=comment,
                created_at=datetime.now(UTC),
            )
        )
        self.record_event(
            owner_user_id=owner_user_id,
            event_type="feedback_submitted",
            trace_id=trace_id,
            payload={"session_id": session_id, "rating": rating},
        )
        return feedback_id
