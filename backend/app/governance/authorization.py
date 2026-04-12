from __future__ import annotations

from fastapi import HTTPException

from app.governance.user_context import UserContext


def require_permission(user_context: UserContext, *, resource: str, action: str) -> None:
    if user_context.has_permission(resource=resource, action=action):
        return
    raise HTTPException(status_code=403, detail=f"Permission denied: {resource}:{action}")
