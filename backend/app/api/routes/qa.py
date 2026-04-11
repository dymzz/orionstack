from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.api.schemas.qa import AskQuestionRequest, AskQuestionResponse, QAHistoryResponse
from app.services.qa_service import QAService

router = APIRouter(tags=["qa"])
service = QAService()


@router.post("/qa/ask", response_model=AskQuestionResponse)
def ask_question(payload: AskQuestionRequest) -> AskQuestionResponse:
    return service.ask(payload)


@router.post("/qa/ask-stream")
def ask_question_stream(payload: AskQuestionRequest) -> StreamingResponse:
    return StreamingResponse(
        service.ask_stream_events(payload),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.get("/qa/history/{session_id}", response_model=QAHistoryResponse)
def get_qa_history(session_id: str) -> QAHistoryResponse:
    return service.list_history(session_id)
