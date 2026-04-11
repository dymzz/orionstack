from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter

from app.api.schemas.session import CreateSessionRequest, SessionResponse

router = APIRouter(tags=["sessions"])


@router.post("/sessions", response_model=SessionResponse)
def create_session(payload: CreateSessionRequest) -> SessionResponse:
    return SessionResponse(
        session_id=str(uuid4()),
        title=payload.title,
        scene=payload.scene,
        created_at=datetime.utcnow(),
    )


@router.get("/sessions")
def list_sessions() -> dict:
    return {"items": []}


@router.get("/sessions/{session_id}")
def get_session(session_id: str) -> dict:
    return {"session_id": session_id}
