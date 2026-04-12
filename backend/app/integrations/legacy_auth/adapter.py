from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.governance.user_context import UserContext, build_default_user_context


class LegacyAuthAdapter:
    """Translate legacy identity data into a stable UserContext contract."""

    def get_user_context(
        self,
        *,
        user_id: str,
        headers: Mapping[str, str] | None = None,
        legacy_payload: Mapping[str, Any] | None = None,
    ) -> UserContext:
        if legacy_payload is None:
            context = build_default_user_context(user_id)
            if headers:
                context.raw_attributes["request_headers"] = dict(headers)
            return context

        raw = dict(legacy_payload)
        roles = [str(item) for item in raw.get("roles", [])]
        departments = [str(item) for item in raw.get("departments", [])]
        context = build_default_user_context(user_id)
        context.username = str(raw.get("username") or raw.get("name") or user_id)
        context.roles = roles or context.roles
        context.departments = departments
        context.raw_attributes = raw
        if headers:
            context.raw_attributes["request_headers"] = dict(headers)
        return context
