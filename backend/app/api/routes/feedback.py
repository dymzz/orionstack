from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request

from app.api.schemas.feedback import FeedbackRequest, FeedbackResponse
from app.core.request_context import get_current_user_id
from app.governance.audit_service import AuditService
from app.models.entities import FeedbackORM
from app.repositories.feedback_repository import FeedbackRepository
from app.repositories.session_repository import SessionRepository

router = APIRouter(tags=["feedback"])
repository = FeedbackRepository()
session_repository = SessionRepository()
audit_service = AuditService()


@router.post("/feedback", response_model=FeedbackResponse)
def submit_feedback(payload: FeedbackRequest, request: Request) -> FeedbackResponse:
    owner_user_id = get_current_user_id(request)
    session = session_repository.get(payload.session_id, owner_user_id=owner_user_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    feedback_id = str(uuid4())
    repository.save(
        FeedbackORM(
            feedback_id=feedback_id,
            owner_user_id=owner_user_id,
            session_id=payload.session_id,
            trace_id=payload.trace_id,
            rating=payload.rating,
            comment=payload.comment,
            created_at=datetime.now(UTC),
        )
    )
    audit_service.log(
        owner_user_id=owner_user_id,
        event_type="feedback_submitted",
        trace_id=payload.trace_id,
        payload={"session_id": payload.session_id, "rating": payload.rating},
    )
    return FeedbackResponse(ok=True, feedback_id=feedback_id)
