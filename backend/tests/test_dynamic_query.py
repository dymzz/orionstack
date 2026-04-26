from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from app.storage.models.dynamic_query import DynamicQuery
from app.storage.repositories.dynamic_query_repo import DynamicQueryRepo
from app.runtime.system_adapter import SystemAdapter
from app.runtime.mock_adapter import MockAdapter
from app.runtime.dynamic_query_service import DynamicQueryService, RuntimePrincipal
from app.schemas.response import DynamicQueryResultItem


class _CapturingAdapter:
    name = "capture"

    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self._rows = rows or [{"name": "ok"}]

    def fetch(self, resource_type: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        self.calls.append({"resource_type": resource_type, "params": params})
        return list(self._rows)


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
        detect_patterns=(r"请假.{0,4}(状态|进度|审批|情况|记录)", r"(我的|查).{0,4}请假"),
        allowed_roles=(),
    )
    defaults.update(overrides)
    return DynamicQuery(**defaults)


def _self_principal(**overrides) -> RuntimePrincipal:
    defaults = dict(tenant_id="default", user_id="u-1", roles=())
    defaults.update(overrides)
    return RuntimePrincipal(**defaults)


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
        assert len(d["detect_patterns"]) == 2
        assert d["source_record_id"] is None
        assert d["allowed_roles"] == []

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

    def test_list_by_source_record(self, repo: DynamicQueryRepo) -> None:
        repo.create(_make_dq(dynamic_query_id="dq-1", source_record_id="sr-001"))
        repo.create(_make_dq(dynamic_query_id="dq-2", source_record_id="sr-002"))

        result = repo.list_by_source_record("sr-001")

        assert len(result) == 1
        assert result[0].dynamic_query_id == "dq-1"

    def test_update_status_by_source_record(self, repo: DynamicQueryRepo) -> None:
        repo.create(_make_dq(dynamic_query_id="dq-1", source_record_id="sr-001"))
        repo.create(_make_dq(dynamic_query_id="dq-2", source_record_id="sr-001"))
        repo.create(_make_dq(dynamic_query_id="dq-3", source_record_id="sr-002"))

        updated = repo.update_status_by_source_record("sr-001", "revoked")

        assert updated == ["dq-1", "dq-2"]
        assert repo.list_by_source_record("sr-001") == []
        assert repo.get("dq-1").status == "revoked"
        assert repo.get("dq-2").status == "revoked"
        assert repo.get("dq-3").status == "active"


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

    def test_default_domain_is_adapter_local(self) -> None:
        from app.runtime.odoo_adapter import OdooAdapter

        adapter = OdooAdapter()
        captured: dict[str, Any] = {}

        def fake_search_read(model, domain, fields, limit):
            captured.update(
                {"model": model, "domain": domain, "fields": fields, "limit": limit}
            )
            return [{"name": "事假"}]

        adapter._search_read = fake_search_read  # type: ignore[method-assign]

        rows = adapter.fetch("leave_status", {})

        assert rows == [{"name": "事假"}]
        assert captured["model"] == "hr.leave"
        assert captured["domain"] == []
        assert captured["limit"] == 10


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
                detect_patterns=(
                    r"(报销|费用).{0,4}(状态|进度|审批|情况|记录)",
                    r"(我的|查).{0,4}(报销|费用)",
                ),
            )
        )
        repo.create(
            _make_dq(
                dynamic_query_id="dq-attendance",
                query_key="attendance_balance",
                resource_type="attendance_balance",
                description="考勤记录",
                detect_patterns=(
                    r"(考勤|打卡|工时).{0,4}(记录|统计|情况|明细)",
                    r"(我的|查).{0,4}考勤",
                ),
            )
        )
        repo.create(
            _make_dq(
                dynamic_query_id="dq-crm",
                query_key="crm_pipeline",
                resource_type="crm_pipeline",
                description="CRM商机",
                scope_type="org",
                detect_patterns=(
                    r"(CRM|商机|客户|销售).{0,4}(状态|进度|情况|列表)",
                    r"(我的|查).{0,4}(商机|客户|销售管线)",
                ),
            )
        )
        adapter = MockAdapter()
        return DynamicQueryService(adapter=adapter, repo=repo)

    def test_detect_leave_status(self, service: DynamicQueryService) -> None:
        assert service.match_query_key("请假状态") == "leave_status"
        assert service.match_query_key("我的请假进度") == "leave_status"

    def test_detect_expense_status_from_repo_patterns(
        self, service: DynamicQueryService
    ) -> None:
        assert service.match_query_key("报销审批情况") == "expense_status"
        assert service.match_query_key("我的费用记录") == "expense_status"

    def test_detect_uses_custom_repo_patterns(self, tmp_path: Path) -> None:
        repo = DynamicQueryRepo(storage_dir=tmp_path / "repo-first")
        repo.create(
            _make_dq(
                dynamic_query_id="dq-travel",
                query_key="travel_expense_status",
                resource_type="travel_expense_form",
                description="差旅报销状态",
                detect_patterns=(r"差旅.{0,4}报销", r"报销单.{0,4}进度"),
            )
        )
        service = DynamicQueryService(adapter=MockAdapter(), repo=repo)

        assert service.match_query_key("差旅报销状态") == "travel_expense_status"
        assert service.match_query_key("报销单进度") == "travel_expense_status"

    def test_detect_does_not_match_without_repo_patterns(
        self, tmp_path: Path
    ) -> None:
        repo = DynamicQueryRepo(storage_dir=tmp_path / "no-patterns")
        repo.create(
            _make_dq(
                dynamic_query_id="dq-no-patterns",
                query_key="expense_status",
                resource_type="expense_status",
                description="报销状态",
                detect_patterns=(),
            )
        )
        service = DynamicQueryService(adapter=MockAdapter(), repo=repo)

        assert service.match_query_key("报销审批情况") is None

    def test_detect_attendance(self, service: DynamicQueryService) -> None:
        assert service.match_query_key("考勤记录") == "attendance_balance"

    def test_detect_crm(self, service: DynamicQueryService) -> None:
        assert service.match_query_key("CRM商机列表") == "crm_pipeline"

    def test_detect_none_for_faq_query(self, service: DynamicQueryService) -> None:
        assert service.match_query_key("如何申请年假？") is None
        assert service.match_query_key("病假需要提交什么材料") is None

    def test_is_allowed_for_active_query(self, service: DynamicQueryService) -> None:
        assert service.is_allowed("leave_status", principal=_self_principal()) is True

    def test_is_not_allowed_without_principal(
        self, service: DynamicQueryService
    ) -> None:
        assert service.is_allowed("leave_status") is False

    def test_self_scope_requires_user_id(self, service: DynamicQueryService) -> None:
        assert (
            service.is_allowed(
                "leave_status",
                principal=_self_principal(user_id=None),
            )
            is False
        )

    def test_tenant_mismatch_is_not_allowed(
        self, service: DynamicQueryService
    ) -> None:
        assert (
            service.is_allowed(
                "leave_status",
                principal=_self_principal(tenant_id="other"),
            )
            is False
        )

    def test_org_scope_requires_user_in_same_tenant(
        self, service: DynamicQueryService
    ) -> None:
        assert service.is_allowed("crm_pipeline", principal=_self_principal()) is True
        assert (
            service.is_allowed(
                "crm_pipeline",
                principal=_self_principal(user_id=None),
            )
            is False
        )

    def test_role_scope_requires_matching_role(self, tmp_path: Path) -> None:
        repo = DynamicQueryRepo(storage_dir=tmp_path / "dq-role")
        repo.create(
            _make_dq(
                dynamic_query_id="dq-role",
                query_key="payroll_status",
                resource_type="payroll_status",
                scope_type="role",
                allowed_roles=("finance_manager",),
            )
        )
        svc = DynamicQueryService(adapter=MockAdapter(), repo=repo)

        assert (
            svc.is_allowed(
                "payroll_status",
                principal=_self_principal(roles=("finance_manager",)),
            )
            is True
        )
        assert (
            svc.is_allowed(
                "payroll_status",
                principal=_self_principal(roles=("employee",)),
            )
            is False
        )

    def test_role_scope_without_allowed_roles_is_denied(
        self, tmp_path: Path
    ) -> None:
        repo = DynamicQueryRepo(storage_dir=tmp_path / "dq-role-empty")
        repo.create(
            _make_dq(
                dynamic_query_id="dq-role-empty",
                query_key="payroll_status",
                resource_type="payroll_status",
                scope_type="role",
            )
        )
        svc = DynamicQueryService(adapter=MockAdapter(), repo=repo)

        assert (
            svc.is_allowed(
                "payroll_status",
                principal=_self_principal(roles=("finance_manager",)),
            )
            is False
        )

    def test_is_not_allowed_for_unknown_key(self, service: DynamicQueryService) -> None:
        assert service.is_allowed("unknown", principal=_self_principal()) is False

    def test_execute_returns_result(self, service: DynamicQueryService) -> None:
        result = service.execute("leave_status", principal=_self_principal())
        assert result is not None
        assert result.query_key == "leave_status"
        assert len(result.data) == 1

    def test_execute_returns_none_for_unknown(self, service: DynamicQueryService) -> None:
        assert service.execute("unknown", principal=_self_principal()) is None

    def test_execute_without_principal_does_not_call_adapter(
        self, tmp_path: Path
    ) -> None:
        adapter = _CapturingAdapter()
        repo = DynamicQueryRepo(storage_dir=tmp_path / "dq-no-principal")
        repo.create(_make_dq())
        svc = DynamicQueryService(adapter=adapter, repo=repo)

        assert svc.execute("leave_status") is None
        assert adapter.calls == []

    def test_execute_sanitizes_id_field(self, tmp_path: Path) -> None:
        adapter = MockAdapter(
            fixtures={"leave_status": [{"id": 99, "name": "test", "state": "validate"}]}
        )
        repo = DynamicQueryRepo(storage_dir=tmp_path / "dq-sanitize")
        repo.create(_make_dq())
        svc = DynamicQueryService(adapter=adapter, repo=repo)
        result = svc.execute("leave_status", principal=_self_principal())
        assert result is not None
        assert "id" not in result.data[0]
        assert result.data[0]["name"] == "test"

    def test_execute_does_not_inject_adapter_specific_domain_param(
        self, tmp_path: Path
    ) -> None:
        adapter = _CapturingAdapter()
        repo = DynamicQueryRepo(storage_dir=tmp_path / "dq-adapter-neutral")
        repo.create(_make_dq())
        svc = DynamicQueryService(adapter=adapter, repo=repo)

        result = svc.execute("leave_status", principal=_self_principal())

        assert result is not None
        assert adapter.calls == [
            {
                "resource_type": "leave_status",
                "params": {"tenant_id": "default", "user_id": "u-1"},
            }
        ]

    def test_execute_copies_params_before_adapter_fetch(self, tmp_path: Path) -> None:
        adapter = _CapturingAdapter()
        repo = DynamicQueryRepo(storage_dir=tmp_path / "dq-param-copy")
        repo.create(_make_dq())
        svc = DynamicQueryService(adapter=adapter, repo=repo)
        params = {"limit": 3}

        result = svc.execute("leave_status", params=params, principal=_self_principal())

        assert result is not None
        assert params == {"limit": 3}
        assert adapter.calls == [
            {
                "resource_type": "leave_status",
                "params": {"limit": 3, "tenant_id": "default", "user_id": "u-1"},
            }
        ]

    def test_execute_principal_overrides_identity_params(self, tmp_path: Path) -> None:
        adapter = _CapturingAdapter()
        repo = DynamicQueryRepo(storage_dir=tmp_path / "dq-param-override")
        repo.create(_make_dq())
        svc = DynamicQueryService(adapter=adapter, repo=repo)
        params = {"tenant_id": "other", "user_id": "attacker", "limit": 3}

        result = svc.execute("leave_status", params=params, principal=_self_principal())

        assert result is not None
        assert params == {"tenant_id": "other", "user_id": "attacker", "limit": 3}
        assert adapter.calls == [
            {
                "resource_type": "leave_status",
                "params": {"tenant_id": "default", "user_id": "u-1", "limit": 3},
            }
        ]


# ---------------------------------------------------------------------------
# Adapter factory
# ---------------------------------------------------------------------------


class TestAdapterFactory:
    def test_settings_default_adapter_is_mock(self, monkeypatch) -> None:
        from app.config.settings import Settings

        monkeypatch.delenv("ORIONSTACK_DYNAMIC_QUERY_ADAPTER", raising=False)

        assert Settings().dynamic_query_adapter == "mock"

    def test_create_default_mock_adapter(self, monkeypatch) -> None:
        from app.config.settings import Settings
        from app.runtime import adapter_factory
        from app.runtime.adapter_factory import create_adapter

        monkeypatch.delenv("ORIONSTACK_DYNAMIC_QUERY_ADAPTER", raising=False)
        s = Settings()
        monkeypatch.setattr(adapter_factory, "settings", s)

        adapter = create_adapter()

        assert adapter.name == "mock"

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
