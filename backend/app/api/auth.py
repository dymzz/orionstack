import base64
import hashlib
import hmac
import json
import time
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config.settings import settings

security = HTTPBearer(auto_error=False)


def authenticate_admin(username: str, password: str) -> bool:
    return secrets_equal(username, settings.admin_username) and secrets_equal(
        password, settings.admin_password
    )


def create_admin_token(username: str) -> str:
    now = int(time.time())
    payload = {
        "sub": username,
        "iat": now,
        "exp": now + settings.admin_token_ttl_seconds,
    }
    payload_part = _urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode())
    signature = _sign(payload_part)
    return f"{payload_part}.{signature}"


def verify_admin_token(token: str) -> str | None:
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
    if not isinstance(username, str) or not isinstance(expires_at, int):
        return None
    if expires_at < int(time.time()):
        return None
    if not secrets_equal(username, settings.admin_username):
        return None
    return username


def require_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> str:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized()
    username = verify_admin_token(credentials.credentials)
    if username is None:
        raise _unauthorized()
    return username


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


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Admin authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )
