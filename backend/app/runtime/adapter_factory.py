from __future__ import annotations

from app.config.settings import settings
from app.runtime.system_adapter import SystemAdapter


def create_adapter() -> SystemAdapter:
    provider = settings.dynamic_query_adapter.strip().lower()

    if provider == "odoo":
        from app.runtime.odoo_adapter import OdooAdapter

        return OdooAdapter(
            url=settings.odoo_url,
            db=settings.odoo_db,
            uid=settings.odoo_uid,
            password=settings.odoo_password,
        )

    if provider == "mock":
        from app.runtime.mock_adapter import MockAdapter

        return MockAdapter()

    raise ValueError(f"Unknown dynamic_query_adapter: {provider!r}")
