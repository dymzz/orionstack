from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from app.storage.models.dynamic_query import DynamicQuery
from app.storage.repositories.dynamic_query_repo import DynamicQueryRepo
from app.runtime.system_adapter import SystemAdapter
from app.runtime.mock_adapter import MockAdapter
from app.runtime.dynamic_query_service import DynamicQueryService
from app.schemas.response import DynamicQueryResultItem


def _make_dq(**overrides) -> DynamicQuery:
    defaults = dict(
        dynamic_query_id="dq-test-001",
        tenant_id="default",
        query_key="leave_status",
        resource_type="leave_status",
        action="read",
        scope_type="self",
        status="active",
        description="请假状态",
    )
    defaults.update(overrides)
    return DynamicQuery(**defaults)


# ---------------------------------------------------------------------------
# DynamicQuery model
# ---------------------------------------------------------------------------


class TestDynamicQueryModel:
    def test_to_dict_roundtrip(self) -> None:
        dq = _make_dq()
        d = dq.to_dict()
        assert d["query_key"] == "leave_status"
        assert d["resource_type"] == "leave_status"
        assert d["action"] == "read"

    def test_frozen_dataclass_rejects_mutation(self) -> None:
        dq = _make_dq()
        with pytest.raises(AttributeError):
            dq.status = "revoked"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# DynamicQueryRepo
# ---------------------------------------------------------------------------


class TestDynamicQueryRepo:
    @pytest.fixture()
    def repo(self, tmp_path: Path) -> DynamicQueryRepo:
        return DynamicQueryRepo(storage_dir=tmp_path)

    def test_create_and_get(self, repo: DynamicQueryRepo) -> None:
        dq = _make_dq()
        repo.create(dq)
        got = repo.get("dq-test-001")
        assert got is not None
        assert got.query_key == "leave_status"

    def test_get_returns_none_for_missing(self, repo: DynamicQueryRepo) -> None:
        assert repo.get("nonexistent") is None

    def test_get_by_query_key(self, repo: DynamicQueryRepo) -> None:
        repo.create(_make_dq(query_key="leave_status"))
        repo.create(_make_dq(dynamic_query_id="dq-2", query_key="expense_status"))
        got = repo.get_by_query_key("leave_status")
        assert got is not None
        assert got.dynamic_query_id == "dq-test-001"

    def test_get_by_query_key_excludes_inactive(self, repo: DynamicQueryRepo) -> None:
        repo.create(_make_dq(status="revoked"))
        assert repo.get_by_query_key("leave_status") is None

    def test_list_active_excludes_inactive(self, repo: DynamicQueryRepo) -> None:
        repo.create(_make_dq(dynamic_query_id="dq-1", status="active"))
        repo.create(_make_dq(dynamic_query_id="dq-2", status="revoked"))
        active = repo.list_active()
        assert len(active) == 1
        assert active[0].dynamic_query_id == "dq-1"

    def test_list_by_resource_type(self, repo: DynamicQueryRepo) -> None:
        repo.create(_make_dq(dynamic_query_id="dq-1", resource_type="leave_status"))
        repo.create(_make_dq(dynamic_query_id="dq-2", resource_type="expense_status"))
        result = repo.list_by_resource_type("leave_status")
        assert len(result) == 1

    def test_upsert_creates_when_missing(self, repo: DynamicQueryRepo) -> None:
        dq = _make_dq()
        repo.upsert(dq)
        assert repo.get("dq-test-001") is not None

    def test_upsert_replaces_by_query_key(self, repo: DynamicQueryRepo) -> None:
        repo.create(_make_dq(description="旧版"))
        repo.upsert(_make_dq(dynamic_query_id="dq-new", description="新版"))
        assert repo.get("dq-test-001") is None
        got = repo.get("dq-new")
        assert got is not None
        assert got.description == "新版"

    def test_update_status(self, repo: DynamicQueryRepo) -> None:
        repo.create(_make_dq())
        repo.update_status("dq-test-001", "revoked")
        got = repo.get("dq-test-001")
        assert got is not None
        assert got.status == "revoked"


# ---------------------------------------------------------------------------
# SystemAdapter Protocol
# ---------------------------------------------------------------------------


class TestSystemAdapterProtocol:
    def test_mock_adapter_satisfies_protocol(self) -> None:
        adapter = MockAdapter()
        assert isinstance(adapter, SystemAdapter)
        assert adapter.name == "mock"

    def test_odoo_adapter_satisfies_protocol(self) -> None:
        from app.runtime.odoo_adapter import OdooAdapter

        adapter = OdooAdapter()
        assert isinstance(adapter, SystemAdapter)
        assert adapter.name == "odoo"


# ---------------------------------------------------------------------------
# MockAdapter
# ---------------------------------------------------------------------------


class TestMockAdapter:
    def test_fetch_returns_fixture_for_known_type(self) -> None:
        adapter = MockAdapter()
        rows = adapter.fetch("leave_status", {})
        assert len(rows) == 1
        assert rows[0]["name"] == "事假"

    def test_fetch_returns_empty_for_unknown_type(self) -> None:
        adapter = MockAdapter()
        assert adapter.fetch("nonexistent", {}) == []

    def test_custom_fixtures(self) -> None:
        fixtures = {"custom_type": [{"key": "val"}]}
        adapter = MockAdapter(fixtures=fixtures)
        rows = adapter.fetch("custom_type", {})
        assert len(rows) == 1
        assert rows[0]["key"] == "val"


# ---------------------------------------------------------------------------
# OdooAdapter — unit tests (no XML-RPC calls)
# ---------------------------------------------------------------------------


class TestOdooAdapterUnit:
    def test_fetch_returns_empty_for_unknown_resource_type(self) -> None:
        from app.runtime.odoo_adapter import OdooAdapter

        adapter = OdooAdapter(model_fields_map={})
        assert adapter.fetch("unknown", {}) == []

    def test_custom_model_fields_map(self) -> None:
        from app.runtime.odoo_adapter import OdooAdapter

        custom_map = {
            "custom_resource": ("custom.model", ["field1", "field2"]),
        }
        adapter = OdooAdapter(model_fields_map=custom_map)
        assert adapter.name == "odoo"
        assert adapter._model_fields_map == custom_map


# ---------------------------------------------------------------------------
# DynamicQueryService
# ---------------------------------------------------------------------------


class TestDynamicQueryService:
    @pytest.fixture()
    def service(self, tmp_path: Path) -> DynamicQueryService:
        repo = DynamicQueryRepo(storage_dir=tmp_path)
        repo.create(_make_dq(query_key="leave_status", resource_type="leave_status"))
        repo.create(
            _make_dq(
                dynamic_query_id="dq-expense",
                query_key="expense_status",
                resource_type="expense_status",
                description="报销状态",
            )
        )
        adapter = MockAdapter()
        return DynamicQueryService(adapter=adapter, repo=repo)

    def test_detect_leave_status(self, service: DynamicQueryService) -> None:
        assert service.detect_query_key("请假状态") == "leave_status"
        assert service.detect_query_key("我的请假进度") == "leave_status"

    def test_detect_expense_status(self, service: DynamicQueryService) -> None:
        assert service.detect_query_key("报销审批情况") == "expense_status"
        assert service.detect_query_key("我的费用记录") == "expense_status"

    def test_detect_attendance(self, service: DynamicQueryService) -> None:
        assert service.detect_query_key("考勤记录") == "attendance_balance"

    def test_detect_crm(self, service: DynamicQueryService) -> None:
        assert service.detect_query_key("CRM商机列表") == "crm_pipeline"

    def test_detect_none_for_faq_query(self, service: DynamicQueryService) -> None:
        assert service.detect_query_key("如何申请年假？") is None
        assert service.detect_query_key("病假需要提交什么材料") is None

    def test_is_allowed_for_active_query(self, service: DynamicQueryService) -> None:
        assert service.is_allowed("leave_status") is True

    def test_is_not_allowed_for_unknown_key(self, service: DynamicQueryService) -> None:
        assert service.is_allowed("unknown") is False

    def test_execute_returns_result(self, service: DynamicQueryService) -> None:
        result = service.execute("leave_status")
        assert result is not None
        assert result.query_key == "leave_status"
        assert len(result.data) == 1

    def test_execute_returns_none_for_unknown(self, service: DynamicQueryService) -> None:
        assert service.execute("unknown") is None

    def test_execute_sanitizes_id_field(self, service: DynamicQueryService) -> None:
        adapter = MockAdapter(
            fixtures={"leave_status": [{"id": 99, "name": "test", "state": "validate"}]}
        )
        repo = DynamicQueryRepo(storage_dir=Path("/tmp/test-dq-sanitize"))
        repo.create(_make_dq())
        svc = DynamicQueryService(adapter=adapter, repo=repo)
        result = svc.execute("leave_status")
        assert result is not None
        assert "id" not in result.data[0]
        assert result.data[0]["name"] == "test"


# ---------------------------------------------------------------------------
# Adapter factory
# ---------------------------------------------------------------------------


class TestAdapterFactory:
    def test_create_mock_adapter(self, monkeypatch) -> None:
        from app.config.settings import Settings
        from app.runtime.adapter_factory import create_adapter

        s = Settings(dynamic_query_adapter="mock")
        monkeypatch.setattr("app.runtime.adapter_factory.settings", s)
        adapter = create_adapter()
        assert adapter.name == "mock"

    def test_create_unknown_raises(self, monkeypatch) -> None:
        from app.config.settings import Settings
        from app.runtime.adapter_factory import create_adapter

        s = Settings(dynamic_query_adapter="nonexistent_system")
        monkeypatch.setattr("app.runtime.adapter_factory.settings", s)

        with pytest.raises(ValueError, match="Unknown dynamic_query_adapter"):
            create_adapter()


# ---------------------------------------------------------------------------
# DynamicQueryResultItem schema
# ---------------------------------------------------------------------------


class TestDynamicQueryResultItemSchema:
    def test_serialization(self) -> None:
        item = DynamicQueryResultItem(
            query_key="leave_status",
            resource_type="leave_status",
            description="请假状态",
            data=[{"state": "validate", "number_of_days": 1.0}],
        )
        d = item.model_dump()
        assert d["query_key"] == "leave_status"
        assert len(d["data"]) == 1

    def test_default_empty_data(self) -> None:
        item = DynamicQueryResultItem(
            query_key="test",
            resource_type="test",
            description="test",
        )
        assert item.data == []
