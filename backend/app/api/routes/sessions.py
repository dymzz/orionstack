from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, HTTPException

from app.api.schemas.session import CreateSessionRequest, SessionListResponse, SessionResponse
from app.models.entities import SessionORM
from app.repositories.session_repository import SessionRepository

router = APIRouter(tags=["sessions"])
repository = SessionRepository()


@router.post("/sessions", response_model=SessionResponse)
def create_session(payload: CreateSessionRequest) -> SessionResponse:
    session = repository.save(
        SessionORM(
            session_id=str(uuid4()),
            title=payload.title,
            scene=payload.scene,
            created_at=datetime.now(UTC),
        )
    )
    return SessionResponse(
        session_id=session.session_id,
        title=session.title,
        scene=session.scene,
        created_at=session.created_at,
    )


@router.get("/sessions", response_model=SessionListResponse)
def list_sessions() -> SessionListResponse:
    return SessionListResponse(
        items=[
            SessionResponse(
                session_id=session.session_id,
                title=session.title,
                scene=session.scene,
                created_at=session.created_at,
            )
            for session in repository.list()
        ]
    )


@router.get("/sessions/{session_id}", response_model=SessionResponse)
def get_session(session_id: str) -> SessionResponse:
    session = repository.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    return SessionResponse(
        session_id=session.session_id,
        title=session.title,
        scene=session.scene,
        created_at=session.created_at,
    )
