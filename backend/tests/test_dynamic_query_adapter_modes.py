from __future__ import annotations

from typing import Any

from app.config.settings import Settings
from app.runtime import adapter_factory
from app.schemas.request import ChatAskRequest
from app.services import chat_service as chat_service_module
from app.services.chat_service import ChatService


class _StaticAdapter:
    def __init__(self, name: str, rows: list[dict[str, Any]]) -> None:
        self._name = name
        self._rows = rows
        self.calls: list[dict[str, Any]] = []

    @property
    def name(self) -> str:
        return self._name

    def fetch(self, resource_type: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        self.calls.append({"resource_type": resource_type, "params": dict(params)})
        return list(self._rows)


def _mode_settings(adapter_name: str) -> Settings:
    return Settings(
        search_backend="local",
        enable_query_planner=False,
        enable_fast_track=False,
        route_confidence_threshold=0.99,
        dynamic_query_adapter=adapter_name,
    )


def _build_chat_service(monkeypatch, adapter_name: str) -> ChatService:
    mode_settings = _mode_settings(adapter_name)
    monkeypatch.setattr(chat_service_module, "settings", mode_settings)
    monkeypatch.setattr(adapter_factory, "settings", mode_settings)
    return ChatService()


def test_factory_default_mode_uses_mock_without_touching_odoo(monkeypatch) -> None:
    from app.runtime.adapter_factory import create_adapter

    monkeypatch.delenv("ORIONSTACK_DYNAMIC_QUERY_ADAPTER", raising=False)
    mode_settings = Settings()
    monkeypatch.setattr(adapter_factory, "settings", mode_settings)

    def fail_if_odoo_selected():
        raise AssertionError("default dynamic query adapter must not touch Odoo")

    monkeypatch.setitem(
        adapter_factory._ADAPTER_FACTORIES, "odoo", fail_if_odoo_selected
    )

    adapter = create_adapter()

    assert mode_settings.dynamic_query_adapter == "mock"
    assert adapter.name == "mock"


def test_factory_explicit_odoo_mode_builds_odoo_adapter_without_network(
    monkeypatch,
) -> None:
    from app.runtime.adapter_factory import create_adapter

    mode_settings = Settings(
        dynamic_query_adapter="odoo",
        odoo_url="http://odoo.example:8069",
        odoo_db="erp",
        odoo_uid=42,
        odoo_password="test-secret",
    )
    monkeypatch.setattr(adapter_factory, "settings", mode_settings)

    adapter = create_adapter()

    assert adapter.name == "odoo"
    assert getattr(adapter, "_url") == "http://odoo.example:8069"
    assert getattr(adapter, "_db") == "erp"
    assert getattr(adapter, "_uid") == 42
    assert getattr(adapter, "_password") == "test-secret"


def test_chat_dynamic_query_default_mock_mode_smoke(monkeypatch) -> None:
    def fail_if_odoo_selected():
        raise AssertionError("mock mode chat smoke must not instantiate Odoo")

    monkeypatch.setitem(
        adapter_factory._ADAPTER_FACTORIES, "odoo", fail_if_odoo_selected
    )
    service = _build_chat_service(monkeypatch, "mock")

    response = service.ask(
        ChatAskRequest(raw_query="我的请假进度", debug=True),
        trace_id="trace-dq-mock",
        debug_enabled=True,
    )

    assert response.response_status == "ok"
    assert response.dynamic_query_result is not None
    assert response.dynamic_query_result.query_key == "leave_status"
    assert response.dynamic_query_result.data[0]["name"] == "事假"
    assert response.debug_info is not None
    assert response.debug_info.router_used == "dynamic_query"
    assert response.debug_info.dynamic_query_key == "leave_status"


def test_chat_dynamic_query_explicit_odoo_mode_uses_configured_adapter(
    monkeypatch,
) -> None:
    adapter = _StaticAdapter(
        "odoo",
        [{"id": 99, "name": "Odoo审批单", "state": "confirm"}],
    )
    monkeypatch.setitem(adapter_factory._ADAPTER_FACTORIES, "odoo", lambda: adapter)

    service = _build_chat_service(monkeypatch, "odoo")

    response = service.ask(
        ChatAskRequest(raw_query="我的请假进度", debug=True),
        trace_id="trace-dq-odoo",
        debug_enabled=True,
    )

    assert adapter.calls == [{"resource_type": "leave_status", "params": {}}]
    assert response.response_status == "ok"
    assert response.dynamic_query_result is not None
    assert response.dynamic_query_result.query_key == "leave_status"
    assert response.dynamic_query_result.data == [
        {"name": "Odoo审批单", "state": "confirm"}
    ]
    assert response.debug_info is not None
    assert response.debug_info.router_used == "dynamic_query"
