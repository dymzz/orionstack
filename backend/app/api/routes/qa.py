from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from app.api.schemas.qa import AskQuestionRequest, AskQuestionResponse, QAHistoryResponse
from app.core.request_context import get_current_user_context
from app.governance.user_context import UserContext
from app.repositories.document_repository import DocumentRepository
from app.repositories.session_repository import SessionRepository
from app.services.qa_service import QAService

router = APIRouter(tags=["qa"])
service = QAService()
session_repository = SessionRepository()
document_repository = DocumentRepository()


def _prepare_owner_scoped_payload(payload: AskQuestionRequest, user_context: UserContext) -> tuple[AskQuestionRequest, str]:
    owner_user_id = user_context.user_id
    session = session_repository.get(payload.session_id, owner_user_id=owner_user_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if not service.supports_scene(session.scene):
        raise HTTPException(status_code=400, detail=f"Unsupported session scene: {session.scene}")

    if not payload.document_ids:
        documents = document_repository.list(owner_user_id=owner_user_id)
        return payload.model_copy(update={"document_ids": [item.document_id for item in documents]}), session.scene

    documents = document_repository.list(payload.document_ids, owner_user_id=owner_user_id)
    if len(documents) != len(payload.document_ids):
        raise HTTPException(status_code=404, detail="Document not found")
    return payload, session.scene


@router.post("/qa/ask", response_model=AskQuestionResponse)
def ask_question(payload: AskQuestionRequest, request: Request) -> AskQuestionResponse:
    user_context = get_current_user_context(request)
    scoped_payload, scene = _prepare_owner_scoped_payload(payload, user_context)
    return service.ask(scoped_payload, user_context=user_context, scene=scene)


@router.post("/qa/ask-stream")
def ask_question_stream(payload: AskQuestionRequest, request: Request) -> StreamingResponse:
    user_context = get_current_user_context(request)
    scoped_payload, scene = _prepare_owner_scoped_payload(payload, user_context)
    return StreamingResponse(
        service.ask_stream_events(scoped_payload, user_context=user_context, scene=scene),
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
    user_context = get_current_user_context(request)
    owner_user_id = user_context.user_id
    session = session_repository.get(session_id, owner_user_id=owner_user_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return service.list_history(
        session_id,
        user_context=user_context,
        limit=limit,
        offset=offset,
        order=order,
    )
