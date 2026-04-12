from __future__ import annotations

import os

from fastapi import Request


DEFAULT_USER_ID = "demo-user"


def get_current_user_id(request: Request) -> str:
    header_value = request.headers.get("X-User-Id", "").strip()
    if header_value:
        return header_value
    return os.getenv("ORIONSTACK_DEFAULT_USER_ID", DEFAULT_USER_ID)
