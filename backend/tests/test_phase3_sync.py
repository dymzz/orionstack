from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

import pytest

from app.runtime.dynamic_query_service import DynamicQueryService
from app.storage.models.action_link import ActionLink
from app.storage.models.dynamic_query import DynamicQuery
from app.storage.models.source_record import SourceRecord
from app.storage.models.import_batch import ImportBatch
from app.storage.models.extraction_candidate import ExtractionCandidate
from app.storage.repositories.action_link_repo import ActionLinkRepo
from app.storage.repositories.dynamic_query_repo import DynamicQueryRepo
from app.storage.repositories.source_record_repo import SourceRecordRepo
from app.storage.repositories.import_batch_repo import ImportBatchRepo
from app.storage.repositories.extraction_candidate_repo import ExtractionCandidateRepo
from app.sync.freshness import check_freshness
from app.sync.sync_parser import parse_export_file
from app.sync.tombstone_handler import handle_tombstone
from app.sync.sync_service import SyncService
from app.extract.llm_extractor import extract_candidates
from app.extract.candidate_reviewer import publish_approved_faq_candidate


# ---------------------------------------------------------------------------
# SourceRecord model
# ---------------------------------------------------------------------------


class TestSourceRecord:
    def test_compute_content_hash_deterministic(self) -> None:
        h1 = SourceRecord.compute_content_hash("hello")
        h2 = SourceRecord.compute_content_hash("hello")
        assert h1 == h2
        assert len(h1) == 16

    def test_compute_content_hash_different_input(self) -> None:
        h1 = SourceRecord.compute_content_hash("hello")
        h2 = SourceRecord.compute_content_hash("world")
        assert h1 != h2

    def test_to_dict_roundtrip(self) -> None:
        sr = SourceRecord(
            source_record_id="sr-test-abc12345",
            tenant_id="default",
            source_system="dingtalk_hr",
            source_object_type="faq_doc",
            external_id="ext-001",
            source_locator="loc-001",
            title="Test",
            raw_content="content",
            content_hash=SourceRecord.compute_content_hash("content"),
            source_updated_at="2026-01-01T00:00:00Z",
            export_batch_id="eb-001",
            access_scope="internal",
            status="active",
            synced_at="2026-01-01T00:00:00Z",
        )
        d = sr.to_dict()
        assert d["source_record_id"] == "sr-test-abc12345"
        assert d["status"] == "active"


# ---------------------------------------------------------------------------
# SourceRecordRepo
# ---------------------------------------------------------------------------


class TestSourceRecordRepo:
    def test_upsert_and_get(self, tmp_path: Path) -> None:
        repo = SourceRecordRepo(storage_dir=tmp_path)
        sr = _make_source_record("sr-001", "ext-001")
        repo.upsert(sr)
        got = repo.get("sr-001")
        assert got is not None
        assert got.source_record_id == "sr-001"

    def test_upsert_replaces_existing(self, tmp_path: Path) -> None:
        repo = SourceRecordRepo(storage_dir=tmp_path)
        sr1 = _make_source_record("sr-001", "ext-001", raw_content="v1")
        sr2 = _make_source_record("sr-002", "ext-001", raw_content="v2")
        repo.upsert(sr1)
        repo.upsert(sr2)
        assert len(repo.list_by_status("active")) == 1
        assert repo.get("sr-002") is not None

    def test_list_by_status(self, tmp_path: Path) -> None:
        repo = SourceRecordRepo(storage_dir=tmp_path)
        repo.upsert(_make_source_record("sr-001", "ext-001"))
        repo.upsert(_make_source_record("sr-002", "ext-002"))
        repo.update_status("sr-001", "revoked")
        active = repo.list_by_status("active")
        assert len(active) == 1
        assert active[0].external_id == "ext-002"

    def test_update_status(self, tmp_path: Path) -> None:
        repo = SourceRecordRepo(storage_dir=tmp_path)
        repo.upsert(_make_source_record("sr-001", "ext-001"))
        repo.update_status("sr-001", "deleted")
        assert repo.get("sr-001") is not None
        assert repo.get("sr-001").status == "deleted"

    def test_list_by_source_system(self, tmp_path: Path) -> None:
        repo = SourceRecordRepo(storage_dir=tmp_path)
        repo.upsert(_make_source_record("sr-001", "ext-001", source_system="dingtalk_hr"))
        repo.upsert(_make_source_record("sr-002", "ext-002", source_system="confluence"))
        dingtalk = repo.list_by_source_system("dingtalk_hr")
        assert len(dingtalk) == 1


# ---------------------------------------------------------------------------
# ImportBatchRepo
# ---------------------------------------------------------------------------


class TestImportBatchRepo:
    def test_create_and_get(self, tmp_path: Path) -> None:
        repo = ImportBatchRepo(storage_dir=tmp_path)
        batch = _make_batch("ib-001")
        repo.create(batch)
        got = repo.get("ib-001")
        assert got is not None
        assert got.status == "running"

    def test_update(self, tmp_path: Path) -> None:
        repo = ImportBatchRepo(storage_dir=tmp_path)
        batch = _make_batch("ib-001")
        repo.create(batch)
        from dataclasses import replace
        finished = _make_batch("ib-001", status="success")
        repo.update(finished)
        assert repo.get("ib-001").status == "success"


# ---------------------------------------------------------------------------
# ExtractionCandidateRepo
# ---------------------------------------------------------------------------


class TestExtractionCandidateRepo:
    def test_create_and_get(self, tmp_path: Path) -> None:
        repo = ExtractionCandidateRepo(storage_dir=tmp_path)
        c = _make_candidate("ec-001", "sr-001")
        repo.create(c)
        got = repo.get("ec-001")
        assert got is not None
        assert got.review_status == "pending"

    def test_update_review_status(self, tmp_path: Path) -> None:
        repo = ExtractionCandidateRepo(storage_dir=tmp_path)
        repo.create(_make_candidate("ec-001", "sr-001"))
        updated = repo.update_review_status("ec-001", "approved", "alice")
        assert updated is not None
        assert updated.review_status == "approved"
        assert updated.reviewed_by == "alice"

    def test_list_by_source_record(self, tmp_path: Path) -> None:
        repo = ExtractionCandidateRepo(storage_dir=tmp_path)
        repo.create(_make_candidate("ec-001", "sr-001"))
        repo.create(_make_candidate("ec-002", "sr-002"))
        result = repo.list_by_source_record("sr-001")
        assert len(result) == 1

    def test_list_by_review_status(self, tmp_path: Path) -> None:
        repo = ExtractionCandidateRepo(storage_dir=tmp_path)
        repo.create(_make_candidate("ec-001", "sr-001"))
        repo.update_review_status("ec-001", "approved")
        pending = repo.list_by_review_status("pending")
        assert len(pending) == 0
        approved = repo.list_by_review_status("approved")
        assert len(approved) == 1


# ---------------------------------------------------------------------------
# Freshness
# ---------------------------------------------------------------------------


class TestFreshness:
    def test_no_limits_is_fresh(self) -> None:
        result = check_freshness(None, None)
        assert result.is_fresh

    def test_within_fresh_until(self) -> None:
        future = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
        result = check_freshness(future, None)
        assert result.is_fresh

    def test_warning_zone(self) -> None:
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        future = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
        result = check_freshness(past, future)
        assert result.is_warning

    def test_stale(self) -> None:
        past1 = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
        past2 = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        result = check_freshness(past1, past2)
        assert result.is_stale


# ---------------------------------------------------------------------------
# SyncParser
# ---------------------------------------------------------------------------


class TestSyncParser:
    def test_parse_json_file(self, tmp_path: Path) -> None:
        items = [
            {
                "external_id": "ext-001",
                "title": "Test FAQ",
                "raw_content": "Q: Hello\nA: World",
                "source_object_type": "faq_doc",
            }
        ]
        f = tmp_path / "export.json"
        f.write_text(json.dumps(items), encoding="utf-8")
        records = parse_export_file(f, "dingtalk_hr", "eb-001")
        assert len(records) == 1
        assert records[0].source_system == "dingtalk_hr"
        assert records[0].content_hash != ""

    def test_parse_jsonl_file(self, tmp_path: Path) -> None:
        f = tmp_path / "export.jsonl"
        f.write_text(
            json.dumps({"external_id": "ext-001", "title": "A"}) + "\n"
            + json.dumps({"external_id": "ext-002", "title": "B"}) + "\n",
            encoding="utf-8",
        )
        records = parse_export_file(f, "confluence", "eb-002")
        assert len(records) == 2


# ---------------------------------------------------------------------------
# SyncService
# ---------------------------------------------------------------------------


class TestSyncService:
    def test_sync_file_creates_batch(self, tmp_path: Path) -> None:
        sr_repo = SourceRecordRepo(storage_dir=tmp_path / "sr")
        ib_repo = ImportBatchRepo(storage_dir=tmp_path / "ib")
        svc = SyncService(sr_repo, ib_repo)

        items = [{"external_id": "ext-001", "title": "FAQ", "raw_content": "c"}]
        f = tmp_path / "export.json"
        f.write_text(json.dumps(items), encoding="utf-8")

        batch = svc.sync_file(f, "dingtalk_hr")
        assert batch.status == "success"
        assert batch.record_count == 1
        assert sr_repo.get is not None

    def test_sync_file_detects_update(self, tmp_path: Path) -> None:
        sr_repo = SourceRecordRepo(storage_dir=tmp_path / "sr")
        ib_repo = ImportBatchRepo(storage_dir=tmp_path / "ib")
        svc = SyncService(sr_repo, ib_repo)

        f1 = tmp_path / "v1.json"
        f1.write_text(json.dumps([{"external_id": "ext-001", "raw_content": "v1"}]), encoding="utf-8")
        svc.sync_file(f1, "dingtalk_hr")

        f2 = tmp_path / "v2.json"
        f2.write_text(json.dumps([{"external_id": "ext-001", "raw_content": "v2"}]), encoding="utf-8")
        batch2 = svc.sync_file(f2, "dingtalk_hr")
        assert batch2.status == "success"

        active = sr_repo.list_by_status("active")
        assert len(active) == 1
        superseded = sr_repo.list_by_status("superseded")
        assert len(superseded) == 1


# ---------------------------------------------------------------------------
# Tombstone
# ---------------------------------------------------------------------------


class TestTombstone:
    def test_tombstone_marks_revoked(self, tmp_path: Path) -> None:
        repo = SourceRecordRepo(storage_dir=tmp_path)
        repo.upsert(_make_source_record("sr-001", "ext-001"))
        handle_tombstone("sr-001", "revoked", repo)
        assert repo.get("sr-001").status == "revoked"

    def test_tombstone_revokes_action_links_by_source_record(
        self, tmp_path: Path
    ) -> None:
        sr_repo = SourceRecordRepo(storage_dir=tmp_path / "sr")
        al_repo = ActionLinkRepo(storage_dir=tmp_path / "al")
        sr_repo.upsert(_make_source_record("sr-001", "ext-001"))
        al_repo.create(_make_action_link("al-1", "sr-001"))
        al_repo.create(_make_action_link("al-2", "sr-002"))

        affected = handle_tombstone(
            "sr-001",
            "revoked",
            sr_repo,
            action_link_repo=al_repo,
        )

        assert affected == ["sr-001", "al-1"]
        assert sr_repo.get("sr-001").status == "revoked"
        assert al_repo.list_by_source_record("sr-001") == []
        assert al_repo.get("al-1").status == "revoked"
        assert al_repo.get("al-2").status == "active"

    def test_tombstone_deletes_action_links_by_source_record(
        self, tmp_path: Path
    ) -> None:
        sr_repo = SourceRecordRepo(storage_dir=tmp_path / "sr")
        al_repo = ActionLinkRepo(storage_dir=tmp_path / "al")
        sr_repo.upsert(_make_source_record("sr-001", "ext-001"))
        al_repo.create(_make_action_link("al-1", "sr-001"))

        handle_tombstone(
            "sr-001",
            "deleted",
            sr_repo,
            action_link_repo=al_repo,
        )

        assert sr_repo.get("sr-001").status == "deleted"
        assert al_repo.list_by_source_record("sr-001") == []
        assert al_repo.get("al-1").status == "deleted"

    def test_tombstone_revokes_dynamic_query_and_blocks_execution(
        self, tmp_path: Path
    ) -> None:
        sr_repo = SourceRecordRepo(storage_dir=tmp_path / "sr")
        dq_repo = DynamicQueryRepo(storage_dir=tmp_path / "dq")
        adapter = _CapturingAdapter()
        service = DynamicQueryService(adapter=adapter, repo=dq_repo)
        sr_repo.upsert(_make_source_record("sr-001", "ext-001"))
        dq_repo.create(_make_dynamic_query("dq-1", "sr-001"))
        dq_repo.create(
            _make_dynamic_query(
                "dq-2",
                "sr-002",
                query_key="expense_status",
                detect_patterns=(r"报销.{0,4}(状态|进度)",),
            )
        )

        assert service.match_query_key("我的请假进度") == "leave_status"

        affected = handle_tombstone(
            "sr-001",
            "revoked",
            sr_repo,
            dynamic_query_repo=dq_repo,
        )

        assert affected == ["sr-001", "dq-1"]
        assert dq_repo.list_by_source_record("sr-001") == []
        assert dq_repo.get("dq-1").status == "revoked"
        assert service.match_query_key("我的请假进度") is None
        assert service.execute("leave_status") is None
        assert adapter.calls == []

    def test_tombstone_deleted_source_revokes_dynamic_query(
        self, tmp_path: Path
    ) -> None:
        sr_repo = SourceRecordRepo(storage_dir=tmp_path / "sr")
        dq_repo = DynamicQueryRepo(storage_dir=tmp_path / "dq")
        sr_repo.upsert(_make_source_record("sr-001", "ext-001"))
        dq_repo.create(_make_dynamic_query("dq-1", "sr-001"))

        handle_tombstone(
            "sr-001",
            "deleted",
            sr_repo,
            dynamic_query_repo=dq_repo,
        )

        assert sr_repo.get("sr-001").status == "deleted"
        assert dq_repo.get("dq-1").status == "revoked"


# ---------------------------------------------------------------------------
# Extract / Publish
# ---------------------------------------------------------------------------


class TestExtract:
    def test_extract_candidates(self) -> None:
        sr = _make_source_record("sr-001", "ext-001", raw_content="Q: How?\nA: Like this.")
        candidates = extract_candidates(
            sr,
            "faq",
            [{"question": "How?", "answer": "Like this.", "_source_span": "Q: How?"}],
        )
        assert len(candidates) == 1
        assert candidates[0].candidate_type == "faq"
        assert candidates[0].review_status == "pending"

    def test_publish_approved_faq(self) -> None:
        sr = _make_source_record("sr-001", "ext-001", import_batch_id="ib-001")
        c = _make_candidate("ec-001", "sr-001", candidate_type="faq")
        unit = publish_approved_faq_candidate(c, sr)
        assert unit.source_record_id == "sr-001"
        assert unit.tenant_id == "default"
        assert unit.import_batch_id == sr.import_batch_id
        assert unit.unit_version == 1
        assert unit.published_at is not None


# ---------------------------------------------------------------------------
# KnowledgeUnit backward compatibility
# ---------------------------------------------------------------------------


class TestKnowledgeUnitPhase3Compat:
    def test_default_phase3_fields(self) -> None:
        from app.storage.repositories.knowledge_unit_repo import KnowledgeUnit
        unit = KnowledgeUnit(
            unit_id="test-001",
            source_kind="faq",
            question="Q?",
            answer="A.",
            body_text="A.",
            keywords=("k",),
            business_domain="hr",
            document_type="faq",
            source_type="manual_faq",
            source_label="HR FAQ",
            source_locator="loc",
            access_scope="internal",
            lifecycle_status="active",
            valid_from="",
            valid_until=None,
            version="v1",
            created_at="",
        )
        assert unit.tenant_id == "default"
        assert unit.source_record_id is None
        assert unit.unit_version == 1
        assert unit.fresh_until is None
        assert unit.stale_after is None
        assert unit.published_at is None

    def test_phase3_fields_in_dict(self) -> None:
        from app.storage.repositories.knowledge_unit_repo import map_faq_item_to_knowledge_unit
        item = {"id": "test-001", "question": "Q?", "answer": "A.", "keywords": []}
        unit = map_faq_item_to_knowledge_unit(item, default_domain="hr")
        d = unit.to_dict()
        assert "tenant_id" in d
        assert "source_record_id" in d
        assert "unit_version" in d
        assert "fresh_until" in d
        assert "stale_after" in d
        assert "import_batch_id" in d
        assert "published_at" in d


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_source_record(
    sr_id: str = "sr-001",
    ext_id: str = "ext-001",
    source_system: str = "dingtalk_hr",
    raw_content: str = "content",
    import_batch_id: str | None = None,
) -> SourceRecord:
    return SourceRecord(
        source_record_id=sr_id,
        tenant_id="default",
        source_system=source_system,
        source_object_type="faq_doc",
        external_id=ext_id,
        source_locator="loc",
        title="Test",
        raw_content=raw_content,
        content_hash=SourceRecord.compute_content_hash(raw_content),
        source_updated_at="2026-01-01T00:00:00Z",
        export_batch_id="eb-001",
        access_scope="internal",
        status="active",
        synced_at="2026-01-01T00:00:00Z",
        import_batch_id=import_batch_id,
    )


def _make_batch(
    batch_id: str = "ib-001",
    status: str = "running",
) -> ImportBatch:
    return ImportBatch(
        import_batch_id=batch_id,
        tenant_id="default",
        source_system="dingtalk_hr",
        mode="incremental",
        started_at="2026-01-01T00:00:00Z",
        status=status,
    )


def _make_candidate(
    candidate_id: str = "ec-001",
    source_record_id: str = "sr-001",
    candidate_type: str = "faq",
) -> ExtractionCandidate:
    return ExtractionCandidate(
        candidate_id=candidate_id,
        tenant_id="default",
        source_record_id=source_record_id,
        candidate_type=candidate_type,
        payload_json='{"question":"Q?","answer":"A."}',
        extractor_model="qwen-plus",
        prompt_version="v1",
        source_span="Q: How?",
        source_span_hash="abc123",
        review_status="pending",
        created_at="2026-01-01T00:00:00Z",
    )


def _make_action_link(
    action_link_id: str,
    source_record_id: str,
) -> ActionLink:
    return ActionLink(
        action_link_id=action_link_id,
        tenant_id="default",
        source_record_id=source_record_id,
        label="去请假系统",
        system_type="manual_export",
        url="https://example.com/leave",
        resource_type="leave_form",
        access_scope="internal",
        status="active",
        published_at="2026-01-01T00:00:00Z",
        business_domains=("hr",),
    )


def _make_dynamic_query(
    dynamic_query_id: str,
    source_record_id: str,
    *,
    query_key: str = "leave_status",
    detect_patterns: tuple[str, ...] = (
        r"请假.{0,4}(状态|进度|审批|情况|记录)",
    ),
) -> DynamicQuery:
    return DynamicQuery(
        dynamic_query_id=dynamic_query_id,
        tenant_id="default",
        query_key=query_key,
        resource_type=query_key,
        action="read",
        scope_type="self",
        status="active",
        description="请假状态",
        detect_patterns=detect_patterns,
        source_record_id=source_record_id,
    )


class _CapturingAdapter:
    name = "capture"

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def fetch(self, resource_type: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        self.calls.append({"resource_type": resource_type, "params": dict(params)})
        return [{"name": "ok"}]
