from __future__ import annotations

from collections.abc import Callable

from app.config.settings import settings
from app.runtime.system_adapter import SystemAdapter

AdapterFactory = Callable[[], SystemAdapter]


def _build_odoo_adapter() -> SystemAdapter:
    from app.runtime.odoo_adapter import OdooAdapter

    return OdooAdapter(
        url=settings.odoo_url,
        db=settings.odoo_db,
        uid=settings.odoo_uid,
        password=settings.odoo_password,
    )


def _build_mock_adapter() -> SystemAdapter:
    from app.runtime.mock_adapter import MockAdapter

    return MockAdapter()


_ADAPTER_FACTORIES: dict[str, AdapterFactory] = {
    "odoo": _build_odoo_adapter,
    "mock": _build_mock_adapter,
}


def create_adapter() -> SystemAdapter:
    provider = settings.dynamic_query_adapter.strip().lower()
    factory = _ADAPTER_FACTORIES.get(provider)
    if factory is None:
        raise ValueError(f"Unknown dynamic_query_adapter: {provider!r}")
    return factory()


def register_adapter(name: str, factory: AdapterFactory) -> None:
    _ADAPTER_FACTORIES[name.strip().lower()] = factory
