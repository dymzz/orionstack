from __future__ import annotations

import os

from fastapi import Request

from app.governance.user_context import UserContext
from app.integrations.legacy_auth.adapter import LegacyAuthAdapter


DEFAULT_USER_ID = "demo-user"
_legacy_auth_adapter = LegacyAuthAdapter()


def get_current_user_id(request: Request) -> str:
    header_value = request.headers.get("X-User-Id", "").strip()
    if header_value:
        return header_value
    return os.getenv("ORIONSTACK_DEFAULT_USER_ID", DEFAULT_USER_ID)


def get_current_user_context(request: Request) -> UserContext:
    user_id = get_current_user_id(request)
    header_map = {key: value for key, value in request.headers.items()}
    return _legacy_auth_adapter.get_user_context(user_id=user_id, headers=header_map)
