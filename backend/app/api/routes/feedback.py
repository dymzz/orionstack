from fastapi import APIRouter, HTTPException, Request

from app.api.schemas.feedback import FeedbackRequest, FeedbackResponse
from app.core.request_context import get_current_user_context
from app.governance.activity_service import ActivityService

router = APIRouter(tags=["feedback"])
service = ActivityService()


@router.post("/feedback", response_model=FeedbackResponse)
def submit_feedback(payload: FeedbackRequest, request: Request) -> FeedbackResponse:
    user_context = get_current_user_context(request)
    owner_user_id = user_context.user_id
    try:
        feedback_id = service.submit_feedback(
            owner_user_id=owner_user_id,
            session_id=payload.session_id,
            trace_id=payload.trace_id,
            rating=payload.rating,
            comment=payload.comment,
        )
    except ValueError:
        raise HTTPException(status_code=404, detail="Session not found")
    return FeedbackResponse(ok=True, feedback_id=feedback_id)
