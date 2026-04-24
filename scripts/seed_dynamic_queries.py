"""Seed DynamicQuery definitions for Odoo resource types.

Run: python -m scripts.seed_dynamic_queries
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.storage.models.dynamic_query import DynamicQuery
from app.storage.repositories.dynamic_query_repo import DynamicQueryRepo

SEEDS: list[dict] = [
    {
        "dynamic_query_id": "dq-leave-status",
        "query_key": "leave_status",
        "resource_type": "leave_status",
        "description": "请假状态",
        "scope_type": "self",
    },
    {
        "dynamic_query_id": "dq-leave-balance",
        "query_key": "leave_balance",
        "resource_type": "leave_status",
        "description": "假期余额",
        "scope_type": "self",
    },
    {
        "dynamic_query_id": "dq-expense-status",
        "query_key": "expense_status",
        "resource_type": "expense_status",
        "description": "报销状态",
        "scope_type": "self",
    },
    {
        "dynamic_query_id": "dq-attendance-balance",
        "query_key": "attendance_balance",
        "resource_type": "attendance_balance",
        "description": "考勤记录",
        "scope_type": "self",
    },
    {
        "dynamic_query_id": "dq-crm-pipeline",
        "query_key": "crm_pipeline",
        "resource_type": "crm_pipeline",
        "description": "CRM商机",
        "scope_type": "org",
    },
]


def main() -> None:
    repo = DynamicQueryRepo()

    for seed in SEEDS:
        dq = DynamicQuery(
            dynamic_query_id=seed["dynamic_query_id"],
            tenant_id="default",
            query_key=seed["query_key"],
            resource_type=seed["resource_type"],
            action="read",
            scope_type=seed.get("scope_type", "self"),
            status="active",
            description=seed["description"],
        )
        repo.upsert(dq)
        print(f"[seed] {dq.query_key}: {dq.description} -> {dq.resource_type}")

    active = repo.list_active()
    print(f"\n[done] {len(active)} active dynamic queries")


if __name__ == "__main__":
    main()
