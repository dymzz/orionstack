from __future__ import annotations

import re
from typing import Any

from app.runtime.system_adapter import SystemAdapter
from app.schemas.response import DynamicQueryResultItem
from app.storage.repositories.dynamic_query_repo import DynamicQueryRepo


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

    def is_allowed(self, query_key: str) -> bool:
        dq = self._repo.get_by_query_key(query_key)
        return dq is not None and dq.status == "active" and dq.action == "read"

    def execute(
        self, query_key: str, params: dict[str, Any] | None = None
    ) -> DynamicQueryResultItem | None:
        dq = self._repo.get_by_query_key(query_key)
        if dq is None:
            return None

        resource_type = dq.resource_type
        fetch_params = dict(params or {})

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
