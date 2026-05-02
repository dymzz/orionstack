from fastapi import APIRouter, Depends, HTTPException, status

from app.api.auth import authenticate_admin, create_admin_token, require_admin
from app.config.settings import settings
from app.schemas.auth import (
    AuthStatusResponse,
    LoginRequest,
    LoginResponse,
    LogoutResponse,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest) -> LoginResponse:
    if not authenticate_admin(payload.username, payload.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    return LoginResponse(
        access_token=create_admin_token(payload.username),
        expires_in=settings.admin_token_ttl_seconds,
        username=payload.username,
    )


@router.get("/me", response_model=AuthStatusResponse)
def get_current_admin(username: str = Depends(require_admin)) -> AuthStatusResponse:
    return AuthStatusResponse(authenticated=True, username=username)


@router.post("/logout", response_model=LogoutResponse)
def logout(_: str = Depends(require_admin)) -> LogoutResponse:
    return LogoutResponse(status="logged_out")
