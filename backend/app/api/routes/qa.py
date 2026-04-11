from fastapi import APIRouter

from app.api.schemas.qa import AskQuestionRequest, AskQuestionResponse
from app.services.qa_service import QAService

router = APIRouter(tags=["qa"])
service = QAService()


@router.post("/qa/ask", response_model=AskQuestionResponse)
def ask_question(payload: AskQuestionRequest) -> AskQuestionResponse:
    return service.ask(payload)


@router.post("/qa/ask-stream")
def ask_question_stream(payload: AskQuestionRequest) -> dict:
    return {"message": "SSE placeholder", "session_id": payload.session_id}


@router.get("/qa/history/{session_id}")
def get_qa_history(session_id: str) -> dict:
    return {"session_id": session_id, "items": []}
