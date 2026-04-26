from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from app.runtime.system_adapter import SystemAdapter
from app.schemas.response import DynamicQueryResultItem
from app.storage.models.dynamic_query import DynamicQuery
from app.storage.repositories.dynamic_query_repo import DynamicQueryRepo


@dataclass(frozen=True)
class RuntimePrincipal:
    tenant_id: str = "default"
    user_id: str | None = None
    roles: tuple[str, ...] = ()


class DynamicQueryService:
    def __init__(
        self,
        adapter: SystemAdapter,
        repo: DynamicQueryRepo | None = None,
    ) -> None:
        self._adapter = adapter
        self._repo = repo or DynamicQueryRepo()

    def match_query_key(self, query: str) -> str | None:
        for dq in self._repo.list_active():
            for pattern in dq.detect_patterns:
                if re.search(pattern, query):
                    return dq.query_key
        return None

    def is_allowed(
        self,
        query_key: str,
        *,
        principal: RuntimePrincipal | None = None,
    ) -> bool:
        dq = self._repo.get_by_query_key(query_key)
        return self._is_allowed_query(dq, principal)

    def execute(
        self,
        query_key: str,
        params: dict[str, Any] | None = None,
        *,
        principal: RuntimePrincipal | None = None,
    ) -> DynamicQueryResultItem | None:
        dq = self._repo.get_by_query_key(query_key)
        if not self._is_allowed_query(dq, principal):
            return None

        resource_type = dq.resource_type
        fetch_params = self._build_fetch_params(dq, principal, params)

        try:
            rows = self._adapter.fetch(resource_type, fetch_params)
        except Exception:
            rows = []

        return DynamicQueryResultItem(
            query_key=query_key,
            resource_type=resource_type,
            description=dq.description,
            data=self._sanitize_rows(rows),
        )

    def _is_allowed_query(
        self,
        dq: DynamicQuery | None,
        principal: RuntimePrincipal | None,
    ) -> bool:
        if dq is None or dq.status != "active" or dq.action != "read":
            return False
        if principal is None:
            return False
        if dq.tenant_id != principal.tenant_id:
            return False
        if dq.scope_type == "self":
            return bool(principal.user_id)
        if dq.scope_type == "org":
            return bool(principal.user_id)
        if dq.scope_type == "role":
            if not principal.user_id or not dq.allowed_roles:
                return False
            return bool(set(dq.allowed_roles) & set(principal.roles))
        return False

    def _build_fetch_params(
        self,
        dq: DynamicQuery,
        principal: RuntimePrincipal,
        params: dict[str, Any] | None,
    ) -> dict[str, Any]:
        fetch_params = dict(params or {})
        fetch_params["tenant_id"] = principal.tenant_id
        if dq.scope_type == "self":
            fetch_params["user_id"] = principal.user_id
        elif dq.scope_type == "role":
            fetch_params["roles"] = list(principal.roles)
        return fetch_params

    def _sanitize_rows(self, rows: list[dict[str, Any]]) -> list[dict]:
        sanitized: list[dict] = []
        for row in rows[:10]:
            item: dict[str, Any] = {}
            for k, v in row.items():
                if k == "id":
                    continue
                if isinstance(v, (str, int, float, bool)):
                    item[k] = v
                elif v is None:
                    item[k] = None
                elif isinstance(v, (list, tuple)):
                    item[k] = str(v)
                elif hasattr(v, "isoformat"):
                    item[k] = v.isoformat()
                else:
                    item[k] = str(v)
            sanitized.append(item)
        return sanitized
