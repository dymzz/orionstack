from uuid import uuid4

from fastapi import APIRouter

from app.api.schemas.feedback import FeedbackRequest, FeedbackResponse

router = APIRouter(tags=["feedback"])


@router.post("/feedback", response_model=FeedbackResponse)
def submit_feedback(payload: FeedbackRequest) -> FeedbackResponse:
    return FeedbackResponse(ok=True, feedback_id=str(uuid4()))
