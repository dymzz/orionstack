from __future__ import annotations

from typing import Any


class MockAdapter:
    _FIXTURES: dict[str, list[dict[str, Any]]] = {
        "leave_status": [
            {
                "name": "事假",
                "state": "validate",
                "date_from": "2025-04-20 09:00:00",
                "date_to": "2025-04-20 18:00:00",
                "number_of_days": 1.0,
            },
        ],
        "expense_status": [
            {
                "name": "交通费",
                "total_amount": 120.0,
                "state": "approve",
                "date": "2025-04-18",
            },
        ],
        "attendance_balance": [
            {
                "check_in": "2025-04-21 09:00:00",
                "check_out": "2025-04-21 18:00:00",
                "worked_hours": 8.0,
            },
        ],
        "crm_pipeline": [
            {
                "name": "测试商机",
                "expected_revenue": 50000.0,
                "probability": 30.0,
            },
        ],
    }

    @property
    def name(self) -> str:
        return "mock"

    def __init__(self, fixtures: dict[str, list[dict[str, Any]]] | None = None) -> None:
        self._fixtures = fixtures if fixtures is not None else self._FIXTURES

    def fetch(self, resource_type: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        return self._fixtures.get(resource_type, [])
