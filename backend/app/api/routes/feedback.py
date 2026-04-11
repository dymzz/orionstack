from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter

from app.api.schemas.feedback import FeedbackRequest, FeedbackResponse
from app.models.entities import FeedbackORM
from app.repositories.feedback_repository import FeedbackRepository

router = APIRouter(tags=["feedback"])
repository = FeedbackRepository()


@router.post("/feedback", response_model=FeedbackResponse)
def submit_feedback(payload: FeedbackRequest) -> FeedbackResponse:
    feedback_id = str(uuid4())
    repository.save(
        FeedbackORM(
            feedback_id=feedback_id,
            session_id=payload.session_id,
            trace_id=payload.trace_id,
            rating=payload.rating,
            comment=payload.comment,
            created_at=datetime.now(UTC),
        )
    )
    return FeedbackResponse(ok=True, feedback_id=feedback_id)
