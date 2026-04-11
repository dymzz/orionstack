from pydantic import BaseModel


class FeedbackRequest(BaseModel):
    session_id: str
    trace_id: str
    rating: str
    comment: str = ""


class FeedbackResponse(BaseModel):
    ok: bool
    feedback_id: str
