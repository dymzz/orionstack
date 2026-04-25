from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class SystemAdapter(Protocol):
    """External system adapter contract for dynamic read queries.

    ``resource_type`` is OrionStack's stable business-resource key. ``params``
    is intentionally adapter-specific so the generic dynamic-query service does
    not need to know vendor query dialects such as XML-RPC domains.
    """

    @property
    def name(self) -> str: ...

    def fetch(self, resource_type: str, params: dict[str, Any]) -> list[dict[str, Any]]: ...
