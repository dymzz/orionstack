from __future__ import annotations

import xmlrpc.client
from typing import Any


_MODEL_FIELDS_MAP: dict[str, tuple[str, list[str]]] = {
    "leave_status": (
        "hr.leave",
        ["name", "holiday_status_id", "date_from", "date_to", "state", "number_of_days"],
    ),
    "expense_status": (
        "hr.expense",
        ["name", "total_amount", "state", "date"],
    ),
    "attendance_balance": (
        "hr.attendance",
        ["check_in", "check_out", "worked_hours"],
    ),
    "crm_pipeline": (
        "crm.lead",
        ["name", "expected_revenue", "stage_id", "probability"],
    ),
}


class OdooAdapter:
    def __init__(
        self,
        url: str = "http://localhost:8069",
        db: str = "odoo",
        uid: int = 2,
        password: str = "qq3938332",
        model_fields_map: dict[str, tuple[str, list[str]]] | None = None,
    ) -> None:
        self._url = url.rstrip("/")
        self._db = db
        self._uid = uid
        self._password = password
        self._model_fields_map = model_fields_map or _MODEL_FIELDS_MAP

    @property
    def name(self) -> str:
        return "odoo"

    def fetch(self, resource_type: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        entry = self._model_fields_map.get(resource_type)
        if entry is None:
            return []
        model, fields = entry
        domain = params.get("domain", [])
        limit = params.get("limit", 10)
        return self._search_read(model, domain, fields, limit)

    def _search_read(
        self,
        model: str,
        domain: list[Any],
        fields: list[str],
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        endpoint = f"{self._url}/xmlrpc/2/object"
        models = xmlrpc.client.ServerProxy(endpoint)
        return models.execute_kw(
            self._db,
            self._uid,
            self._password,
            model,
            "search_read",
            [domain],
            {"fields": fields, "limit": limit},
        )
