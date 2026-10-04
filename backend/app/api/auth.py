import base64
import hashlib
import hmac
import json
import time
from typing import Any

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, APIKeyCookie
from app.account.settings import IdentitySettings

from app.config.settings import settings

security = HTTPBearer(auto_error=False,description="Legacy CLI compatibility in local demo mode only")
session_security = APIKeyCookie(name=IdentitySettings().cookie_name,scheme_name="BrowserSession",auto_error=False,
    description="Opaque HttpOnly server session; production cookie uses __Host- prefix. Writes require Origin + X-CSRF-Token.")


def authenticate_user(username: str, password: str) -> tuple[bool, str]:
    from app.account.boundary import get_identity_settings
    if get_identity_settings().mode != "demo":
        return False, ""
    account = settings.user_accounts.get(username)
    if account is None:
        return False, ""
    stored_password, role = account
    if secrets_equal(password, stored_password):
        return True, role
    return False, ""


def create_token(username: str, role: str) -> str:
    now = int(time.time())
    payload = {
        "sub": username,
        "role": role,
        "iat": now,
        "exp": now + settings.admin_token_ttl_seconds,
    }
    payload_part = _urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode())
    signature = _sign(payload_part)
    return f"{payload_part}.{signature}"


def verify_token(token: str) -> dict[str, Any] | None:
    from app.account.boundary import get_identity_settings
    if get_identity_settings().mode != "demo":
        return None
    try:
        payload_part, signature = token.split(".", 1)
    except ValueError:
        return None

    expected_signature = _sign(payload_part)
    if not secrets_equal(signature, expected_signature):
        return None

    try:
        payload = json.loads(_urlsafe_b64decode(payload_part))
    except (ValueError, json.JSONDecodeError):
        return None

    username = payload.get("sub")
    expires_at = payload.get("exp")
    role = payload.get("role", "admin")
    if not isinstance(username, str) or not isinstance(expires_at, int):
        return None
    if expires_at < int(time.time()):
        return None
    stored_password, expected_role = settings.user_accounts.get(username, ("", ""))
    if not stored_password:
        return None
    return {"username": username, "role": expected_role}


def require_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    request: Request = None,
    session_cookie: str | None = Depends(session_security),
) -> dict[str, Any]:
    from app.account.boundary import get_identity_settings, session_user
    config = get_identity_settings()
    if request is not None and (config.mode == "oidc" or request.cookies.get(config.cookie_name)):
        return session_user(request)
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized("Authentication required")
    result = verify_token(credentials.credentials)
    if result is None:
        raise _unauthorized("Authentication required")
    return result


def require_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    request: Request = None,
    session_cookie: str | None = Depends(session_security),
) -> str:
    result = require_user(credentials,request)
    if result["role"] != "admin":
        raise _forbidden("Admin access required")
    return result["username"]


def secrets_equal(left: str, right: str) -> bool:
    return hmac.compare_digest(left.encode(), right.encode())


def _sign(payload_part: str) -> str:
    digest = hmac.new(
        settings.admin_token_secret.encode(),
        payload_part.encode(),
        hashlib.sha256,
    ).digest()
    return _urlsafe_b64encode(digest)


def _urlsafe_b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def _urlsafe_b64decode(value: str) -> bytes:
    padded = value + "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(padded.encode())


def _unauthorized(detail: str = "Authentication required") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _forbidden(detail: str = "Insufficient permissions") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=detail,
    )
