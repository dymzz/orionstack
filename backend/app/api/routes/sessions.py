from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request

from app.api.schemas.session import CreateSessionRequest, SessionListResponse, SessionResponse
from app.core.request_context import get_current_user_context
from app.governance.audit_service import AuditService
from app.models.entities import SessionORM
from app.repositories.session_repository import SessionRepository

router = APIRouter(tags=["sessions"])
repository = SessionRepository()
audit_service = AuditService()


@router.post("/sessions", response_model=SessionResponse)
def create_session(payload: CreateSessionRequest, request: Request) -> SessionResponse:
    user_context = get_current_user_context(request)
    owner_user_id = user_context.user_id
    session = repository.save(
        SessionORM(
            session_id=str(uuid4()),
            owner_user_id=owner_user_id,
            title=payload.title,
            scene=payload.scene,
            created_at=datetime.now(UTC),
        )
    )
    audit_service.log(
        owner_user_id=owner_user_id,
        event_type="session_created",
        payload={"session_id": session.session_id, "scene": session.scene},
    )
    return SessionResponse(
        session_id=session.session_id,
        title=session.title,
        scene=session.scene,
        created_at=session.created_at,
    )


@router.get("/sessions", response_model=SessionListResponse)
def list_sessions(request: Request) -> SessionListResponse:
    user_context = get_current_user_context(request)
    owner_user_id = user_context.user_id
    return SessionListResponse(
        items=[
            SessionResponse(
                session_id=session.session_id,
                title=session.title,
                scene=session.scene,
                created_at=session.created_at,
            )
            for session in repository.list(owner_user_id=owner_user_id)
        ]
    )


@router.get("/sessions/{session_id}", response_model=SessionResponse)
def get_session(session_id: str, request: Request) -> SessionResponse:
    user_context = get_current_user_context(request)
    owner_user_id = user_context.user_id
    session = repository.get(session_id, owner_user_id=owner_user_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    return SessionResponse(
        session_id=session.session_id,
        title=session.title,
        scene=session.scene,
        created_at=session.created_at,
    )
