from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from app.governance.user_context import UserContext


@dataclass(slots=True)
class ToolCallRequest:
    tool_name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    required_permission: tuple[str, str] | None = None
    trace_id: str = ""


@dataclass(slots=True)
class ToolCallResult:
    ok: bool
    data: dict[str, Any] = field(default_factory=dict)
    error_code: str = ""
    error_message: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


class ToolGateway:
    def __init__(self) -> None:
        self._handlers: dict[str, Callable[[ToolCallRequest, UserContext], ToolCallResult | dict[str, Any]]] = {}

    def register(
        self,
        tool_name: str,
        handler: Callable[[ToolCallRequest, UserContext], ToolCallResult | dict[str, Any]],
    ) -> None:
        self._handlers[tool_name] = handler

    def execute(self, request: ToolCallRequest, *, user_context: UserContext) -> ToolCallResult:
        if request.required_permission is not None:
            resource, action = request.required_permission
            if not user_context.has_permission(resource=resource, action=action):
                return ToolCallResult(
                    ok=False,
                    error_code="permission_denied",
                    error_message=f"Permission denied for {resource}:{action}",
                )

        handler = self._handlers.get(request.tool_name)
        if handler is None:
            return ToolCallResult(
                ok=False,
                error_code="tool_not_registered",
                error_message=f"Tool not registered: {request.tool_name}",
            )

        try:
            result = handler(request, user_context)
        except Exception as exc:
            return ToolCallResult(
                ok=False,
                error_code="tool_execution_failed",
                error_message=str(exc),
            )

        if isinstance(result, ToolCallResult):
            return result

        return ToolCallResult(ok=True, data=dict(result), raw=dict(result))
