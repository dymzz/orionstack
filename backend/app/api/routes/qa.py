from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from app.api.schemas.qa import AskQuestionRequest, AskQuestionResponse, QAHistoryResponse
from app.core.request_context import get_current_user_id
from app.repositories.document_repository import DocumentRepository
from app.repositories.session_repository import SessionRepository
from app.services.qa_service import QAService

router = APIRouter(tags=["qa"])
service = QAService()
session_repository = SessionRepository()
document_repository = DocumentRepository()


def _prepare_owner_scoped_payload(payload: AskQuestionRequest, owner_user_id: str) -> AskQuestionRequest:
    session = session_repository.get(payload.session_id, owner_user_id=owner_user_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    if not payload.document_ids:
        documents = document_repository.list(owner_user_id=owner_user_id)
        return payload.model_copy(update={"document_ids": [item.document_id for item in documents]})

    documents = document_repository.list(payload.document_ids, owner_user_id=owner_user_id)
    if len(documents) != len(payload.document_ids):
        raise HTTPException(status_code=404, detail="Document not found")
    return payload


@router.post("/qa/ask", response_model=AskQuestionResponse)
def ask_question(payload: AskQuestionRequest, request: Request) -> AskQuestionResponse:
    owner_user_id = get_current_user_id(request)
    scoped_payload = _prepare_owner_scoped_payload(payload, owner_user_id)
    return service.ask(scoped_payload, owner_user_id=owner_user_id)


@router.post("/qa/ask-stream")
def ask_question_stream(payload: AskQuestionRequest, request: Request) -> StreamingResponse:
    owner_user_id = get_current_user_id(request)
    scoped_payload = _prepare_owner_scoped_payload(payload, owner_user_id)
    return StreamingResponse(
        service.ask_stream_events(scoped_payload, owner_user_id=owner_user_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.get("/qa/history/{session_id}", response_model=QAHistoryResponse)
def get_qa_history(
    session_id: str,
    request: Request,
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    order: Literal["asc", "desc"] = Query(default="desc"),
) -> QAHistoryResponse:
    owner_user_id = get_current_user_id(request)
    session = session_repository.get(session_id, owner_user_id=owner_user_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return service.list_history(
        session_id,
        owner_user_id=owner_user_id,
        limit=limit,
        offset=offset,
        order=order,
    )
