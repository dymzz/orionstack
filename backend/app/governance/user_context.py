from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class Permission:
    resource: str
    action: str


@dataclass(slots=True)
class UserContext:
    user_id: str
    username: str
    departments: list[str] = field(default_factory=list)
    roles: list[str] = field(default_factory=list)
    raw_attributes: dict[str, Any] = field(default_factory=dict)
    permissions: list[Permission] = field(default_factory=list)

    def has_permission(self, *, resource: str, action: str) -> bool:
        return any(
            permission.resource == resource and permission.action == action
            for permission in self.permissions
        )

    def to_state_payload(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "username": self.username,
            "departments": list(self.departments),
            "roles": list(self.roles),
            "raw_attributes": dict(self.raw_attributes),
            "permissions": [
                {"resource": permission.resource, "action": permission.action}
                for permission in self.permissions
            ],
        }


def build_default_user_context(user_id: str) -> UserContext:
    return UserContext(
        user_id=user_id,
        username=user_id,
        roles=["user"],
        raw_attributes={"source": "default_header"},
        permissions=[
            Permission(resource="qa", action="ask"),
            Permission(resource="document", action="read"),
            Permission(resource="document", action="write"),
            Permission(resource="feedback", action="write"),
            Permission(resource="audit", action="read"),
        ],
    )
