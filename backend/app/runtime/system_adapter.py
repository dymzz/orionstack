from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class SystemAdapter(Protocol):
    @property
    def name(self) -> str: ...

    def fetch(self, resource_type: str, params: dict[str, Any]) -> list[dict[str, Any]]: ...
