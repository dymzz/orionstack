from __future__ import annotations

import re
from typing import Any

from app.runtime.system_adapter import SystemAdapter
from app.schemas.response import DynamicQueryResultItem
from app.storage.repositories.dynamic_query_repo import DynamicQueryRepo


_DYNAMIC_QUERY_PATTERNS: list[tuple[str, str]] = [
    (r"请假.{0,4}(状态|进度|审批|情况|记录)", "leave_status"),
    (r"(我的|查).{0,4}请假", "leave_status"),
    (r"(年假|病假|事假|调休).{0,4}(余额|剩余|还有多少|剩多少|天数)", "leave_balance"),
    (r"(报销|费用).{0,4}(状态|进度|审批|情况|记录)", "expense_status"),
    (r"(我的|查).{0,4}(报销|费用)", "expense_status"),
    (r"(考勤|打卡|工时).{0,4}(记录|统计|情况|明细)", "attendance_balance"),
    (r"(我的|查).{0,4}考勤", "attendance_balance"),
    (r"(CRM|商机|客户|销售).{0,4}(状态|进度|情况|列表)", "crm_pipeline"),
    (r"(我的|查).{0,4}(商机|客户|销售管线)", "crm_pipeline"),
]


class DynamicQueryService:
    def __init__(
        self,
        adapter: SystemAdapter,
        repo: DynamicQueryRepo | None = None,
    ) -> None:
        self._adapter = adapter
        self._repo = repo or DynamicQueryRepo()

    def detect_query_key(self, query: str) -> str | None:
        for pattern, query_key in _DYNAMIC_QUERY_PATTERNS:
            if re.search(pattern, query):
                return query_key
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
        fetch_params = params or {}
        if "domain" not in fetch_params:
            fetch_params["domain"] = []

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
