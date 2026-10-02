from fastapi import APIRouter, Depends, HTTPException, status

from app.api.auth import authenticate_user, create_token, require_admin, require_user
from app.config.settings import settings
from app.observability.logging import get_logger
from app.schemas.auth import (
    AuthStatusResponse,
    LoginRequest,
    LoginResponse,
    LogoutResponse,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
logger = get_logger("orionstack.auth")


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest) -> LoginResponse:
    success, role = authenticate_user(payload.username, payload.password)
    if not success:
        logger.warning("login_failed username=%s", payload.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    logger.info("login_succeeded username=%s role=%s", payload.username, role)
    return LoginResponse(
        access_token=create_token(payload.username, role),
        expires_in=settings.admin_token_ttl_seconds,
        username=payload.username,
        role=role,
    )


@router.get("/me", response_model=AuthStatusResponse)
def get_current_user(user: dict = Depends(require_user)) -> AuthStatusResponse:
    return AuthStatusResponse(
        authenticated=True, username=user["username"], role=user["role"]
    )


@router.post("/logout", response_model=LogoutResponse)
def logout(user: dict = Depends(require_user)) -> LogoutResponse:
    logger.info("logout username=%s role=%s", user["username"], user["role"])
    return LogoutResponse(status="logged_out")