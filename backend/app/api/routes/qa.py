from typing import Literal

from fastapi import APIRouter, Query
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
def get_qa_history(
    session_id: str,
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    order: Literal["asc", "desc"] = Query(default="desc"),
) -> QAHistoryResponse:
    return service.list_history(
        session_id,
        limit=limit,
        offset=offset,
        order=order,
    )
