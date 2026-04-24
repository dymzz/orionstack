"""Seed ActionLink data from Odoo module URLs.

Maps each Odoo module to the business domains and FAQ topics it covers.
Generates one ActionLink per module at the module-level entry point.
Run: python -m scripts.seed_action_links
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.storage.models.action_link import ActionLink
from app.storage.repositories.action_link_repo import ActionLinkRepo

ODOO_BASE = "http://localhost:8069/odoo"

SEEDS: list[dict] = [
    {
        "action_link_id": "al-odoo-time-off",
        "label": "去请假系统",
        "url": f"{ODOO_BASE}/time-off",
        "resource_type": "leave_form",
        "system_type": "odoo",
        "access_scope": "internal",
        "business_domains": ["hr"],
    },
    {
        "action_link_id": "al-odoo-attendances",
        "label": "去考勤系统",
        "url": f"{ODOO_BASE}/attendances",
        "resource_type": "attendance_record",
        "system_type": "odoo",
        "access_scope": "internal",
        "business_domains": ["hr"],
    },
    {
        "action_link_id": "al-odoo-employees",
        "label": "去员工管理系统",
        "url": f"{ODOO_BASE}/employees",
        "resource_type": "employee_profile",
        "system_type": "odoo",
        "access_scope": "internal",
        "business_domains": ["hr", "admin"],
    },
    {
        "action_link_id": "al-odoo-expense",
        "label": "去报销系统",
        "url": f"{ODOO_BASE}/expenses",
        "resource_type": "expense_form",
        "system_type": "odoo",
        "access_scope": "internal",
        "business_domains": ["finance"],
    },
    {
        "action_link_id": "al-odoo-invoices",
        "label": "去发票系统",
        "url": f"{ODOO_BASE}/customer-invoices",
        "resource_type": "invoice_list",
        "system_type": "odoo",
        "access_scope": "internal",
        "business_domains": ["finance"],
    },
    {
        "action_link_id": "al-odoo-crm",
        "label": "去 CRM",
        "url": f"{ODOO_BASE}/crm",
        "resource_type": "crm_pipeline",
        "system_type": "odoo",
        "access_scope": "internal",
        "business_domains": ["sales"],
    },
    {
        "action_link_id": "al-odoo-project",
        "label": "去项目管理系统",
        "url": f"{ODOO_BASE}/project",
        "resource_type": "project_board",
        "system_type": "odoo",
        "access_scope": "internal",
        "business_domains": ["product", "it"],
    },
]


def main() -> None:
    repo = ActionLinkRepo()
    now = datetime.now(timezone.utc).isoformat()

    for seed in SEEDS:
        link = ActionLink(
            action_link_id=seed["action_link_id"],
            tenant_id="default",
            source_record_id="",
            label=seed["label"],
            system_type=seed["system_type"],
            url=seed["url"],
            resource_type=seed["resource_type"],
            access_scope=seed["access_scope"],
            status="active",
            published_at=now,
            business_domains=tuple(seed.get("business_domains", [])),
        )
        repo.upsert(link)
        print(f"[seed] {link.action_link_id}: {link.label} -> {link.url}")

    active = repo.list_active()
    print(f"\n[done] {len(active)} active action links")


if __name__ == "__main__":
    main()
