from __future__ import annotations

from pathlib import Path

import pytest

from app.storage.models.action_link import ActionLink
from app.storage.repositories.action_link_repo import ActionLinkRepo
from app.schemas.response import ActionLinkItem


def _make_link(**overrides) -> ActionLink:
    defaults = dict(
        action_link_id="al-test-001",
        tenant_id="default",
        source_record_id="sr-test-001",
        label="请假申请",
        system_type="odoo",
        url="http://localhost:8069/odoo/leave",
        resource_type="leave_form",
        access_scope="internal",
        status="active",
        published_at="2025-01-01T00:00:00Z",
        fresh_until=None,
        business_domains=("hr",),
    )
    defaults.update(overrides)
    return ActionLink(**defaults)


class TestActionLinkModel:
    def test_to_dict_roundtrip(self) -> None:
        link = _make_link()
        d = link.to_dict()
        assert d["action_link_id"] == "al-test-001"
        assert d["label"] == "请假申请"
        assert d["resource_type"] == "leave_form"
        assert d["fresh_until"] is None
        assert d["business_domains"] == ["hr"]

    def test_frozen_dataclass_rejects_mutation(self) -> None:
        link = _make_link()
        with pytest.raises(AttributeError):
            link.label = "changed"  # type: ignore[misc]


class TestActionLinkRepo:
    @pytest.fixture()
    def repo(self, tmp_path: Path) -> ActionLinkRepo:
        return ActionLinkRepo(storage_dir=tmp_path)

    def test_create_and_get(self, repo: ActionLinkRepo) -> None:
        link = _make_link()
        repo.create(link)
        got = repo.get("al-test-001")
        assert got is not None
        assert got.label == "请假申请"

    def test_get_returns_none_for_missing(self, repo: ActionLinkRepo) -> None:
        assert repo.get("nonexistent") is None

    def test_list_active_excludes_inactive(self, repo: ActionLinkRepo) -> None:
        repo.create(_make_link(action_link_id="al-1", status="active"))
        repo.create(_make_link(action_link_id="al-2", status="revoked"))
        active = repo.list_active()
        assert len(active) == 1
        assert active[0].action_link_id == "al-1"

    def test_list_by_resource_type_filters_correctly(self, repo: ActionLinkRepo) -> None:
        repo.create(_make_link(action_link_id="al-1", resource_type="leave_form"))
        repo.create(_make_link(action_link_id="al-2", resource_type="expense_form"))
        repo.create(
            _make_link(action_link_id="al-3", resource_type="leave_form", status="revoked")
        )
        result = repo.list_by_resource_type("leave_form")
        assert len(result) == 1
        assert result[0].action_link_id == "al-1"

    def test_list_by_source_record(self, repo: ActionLinkRepo) -> None:
        repo.create(_make_link(action_link_id="al-1", source_record_id="sr-001"))
        repo.create(_make_link(action_link_id="al-2", source_record_id="sr-002"))
        result = repo.list_by_source_record("sr-001")
        assert len(result) == 1
        assert result[0].source_record_id == "sr-001"

    def test_upsert_creates_when_missing(self, repo: ActionLinkRepo) -> None:
        link = _make_link()
        repo.upsert(link)
        assert repo.get("al-test-001") is not None

    def test_upsert_replaces_by_id(self, repo: ActionLinkRepo) -> None:
        repo.create(_make_link(action_link_id="al-same", label="旧版"))
        repo.upsert(_make_link(action_link_id="al-same", label="新版"))
        got = repo.get("al-same")
        assert got is not None
        assert got.label == "新版"

    def test_upsert_allows_multiple_links_same_system_and_resource(
        self, repo: ActionLinkRepo
    ) -> None:
        repo.create(_make_link(action_link_id="al-1", label="入口一"))
        repo.upsert(_make_link(action_link_id="al-2", label="入口二"))
        links = repo.list_by_resource_type("leave_form")
        assert len(links) == 2

    def test_update_status(self, repo: ActionLinkRepo) -> None:
        repo.create(_make_link())
        repo.update_status("al-test-001", "revoked")
        got = repo.get("al-test-001")
        assert got is not None
        assert got.status == "revoked"

    def test_update_status_by_source_record(self, repo: ActionLinkRepo) -> None:
        repo.create(_make_link(action_link_id="al-1", source_record_id="sr-001"))
        repo.create(_make_link(action_link_id="al-2", source_record_id="sr-001"))
        repo.create(_make_link(action_link_id="al-3", source_record_id="sr-002"))

        updated = repo.update_status_by_source_record("sr-001", "revoked")

        assert updated == ["al-1", "al-2"]
        assert repo.list_by_source_record("sr-001") == []
        assert repo.get("al-1").status == "revoked"
        assert repo.get("al-2").status == "revoked"
        assert repo.get("al-3").status == "active"

    def test_list_active_empty_on_fresh_repo(self, repo: ActionLinkRepo) -> None:
        assert repo.list_active() == []


class TestFindActionLinks:
    def test_none_domain_returns_empty(self) -> None:
        from app.services.action_link_resolver import ActionLinkResolver

        resolver = ActionLinkResolver()
        result = resolver.find_by_domain(None)
        assert result == []

    def test_unknown_domain_returns_empty(self) -> None:
        from app.services.action_link_resolver import ActionLinkResolver

        resolver = ActionLinkResolver()
        result = resolver.find_by_domain("unknown_domain")
        assert result == []

    def test_hr_domain_maps_resource_types(self, tmp_path: Path, monkeypatch) -> None:
        from app.services.action_link_resolver import ActionLinkResolver

        repo = ActionLinkRepo(storage_dir=tmp_path)
        repo.create(
            _make_link(
                action_link_id="al-hr-leave",
                label="请假申请",
                url="http://localhost:8069/odoo/leave",
                resource_type="leave_form",
                business_domains=("hr",),
            )
        )
        monkeypatch.setattr(
            "app.storage.repositories.action_link_repo._STORAGE_DIR", tmp_path
        )

        resolver = ActionLinkResolver(repo=repo)
        result = resolver.find_by_domain("hr")
        assert len(result) >= 1
        assert any(li.label == "请假申请" for li in result)

    def test_action_link_item_schema(self) -> None:
        item = ActionLinkItem(
            action_link_id="al-1",
            label="Test",
            url="http://example.com",
            system_type="odoo",
            resource_type="leave_form",
        )
        d = item.model_dump()
        assert d["action_link_id"] == "al-1"
        assert d["system_type"] == "odoo"
