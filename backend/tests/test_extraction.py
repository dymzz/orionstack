from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.extract.prompt_templates import build_extraction_messages, parse_extraction_response
from app.extract.llm_extractor import extract_candidates
from app.extract.candidate_reviewer import review_candidate, publish_candidate
from app.storage.models.source_record import SourceRecord
from app.storage.models.extraction_candidate import ExtractionCandidate
from app.storage.repositories.extraction_candidate_repo import ExtractionCandidateRepo
from app.storage.repositories.source_record_repo import SourceRecordRepo
from app.storage.repositories.action_link_repo import ActionLinkRepo
from app.storage.repositories.dynamic_query_repo import DynamicQueryRepo
from app.schemas.extraction import ExtractRequest, ExtractResponse, ReviewRequest, ReviewResponse
from app.extract.providers.openai_compatible_provider import ExtractionProvider


def _make_source_record(**overrides) -> SourceRecord:
    defaults = dict(
        source_record_id="sr-test-001",
        tenant_id="default",
        source_system="odoo",
        source_object_type="faq_doc",
        external_id="ext-001",
        source_locator="loc-001",
        title="请假制度说明",
        raw_content="员工请假需要提前在系统中提交申请。年假每年有12天，病假需要提供医生证明。请假审批由直属上级负责。",
        content_hash=SourceRecord.compute_content_hash("test"),
        source_updated_at="2025-01-01T00:00:00Z",
        export_batch_id="batch-001",
        access_scope="internal",
        status="active",
        synced_at="2025-01-01T00:00:00Z",
    )
    defaults.update(overrides)
    return SourceRecord(**defaults)


def _make_candidate(**overrides) -> ExtractionCandidate:
    defaults = dict(
        candidate_id="ec-test001abc",
        tenant_id="default",
        source_record_id="sr-test-001",
        candidate_type="faq",
        payload_json='{"candidate_type": "faq", "question": "如何请假？", "answer": "在系统中提交申请", "keywords": ["请假", "申请"], "business_domain": "hr"}',
        extractor_model="qwen-plus",
        prompt_version="v1",
        source_span="请假制度说明",
        source_span_hash="abc123",
        review_status="pending",
        created_at="2025-01-01T00:00:00Z",
    )
    defaults.update(overrides)
    return ExtractionCandidate(**defaults)


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------


class TestPromptTemplates:
    def test_build_messages_faq_only(self) -> None:
        msgs = build_extraction_messages("some content", ["faq"])
        assert len(msgs) == 2
        assert msgs[0]["role"] == "system"
        assert "FAQ" in msgs[1]["content"]

    def test_build_messages_all_types(self) -> None:
        msgs = build_extraction_messages("some content")
        user_content = msgs[1]["content"]
        assert "faq" in user_content.lower() or "FAQ" in user_content
        assert "action_link" in user_content or "操作入口" in user_content
        assert "dynamic_query" in user_content or "动态状态" in user_content

    def test_parse_extraction_response_valid(self) -> None:
        raw = json.dumps({
            "candidates": [
                {"candidate_type": "faq", "question": "Q?", "answer": "A.", "keywords": ["k"], "business_domain": "hr"},
            ]
        })
        result = parse_extraction_response(raw)
        assert len(result) == 1
        assert result[0]["candidate_type"] == "faq"

    def test_parse_extraction_response_empty(self) -> None:
        assert parse_extraction_response('{"candidates": []}') == []

    def test_parse_extraction_response_invalid_json(self) -> None:
        assert parse_extraction_response("not json") == []

    def test_parse_extraction_response_fenced(self) -> None:
        raw = '```json\n{"candidates": [{"candidate_type": "faq", "question": "Q?", "answer": "A."}]}\n```'
        result = parse_extraction_response(raw)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# LLM extractor
# ---------------------------------------------------------------------------


class TestLlmExtractor:
    def test_extract_candidates_creates_pending(self) -> None:
        sr = _make_source_record()
        payloads = [
            {"candidate_type": "faq", "question": "Q?", "answer": "A.", "keywords": ["k"], "_source_span": "span1"},
        ]
        candidates = extract_candidates(sr, "faq", payloads)
        assert len(candidates) == 1
        assert candidates[0].review_status == "pending"
        assert candidates[0].candidate_type == "faq"
        payload = json.loads(candidates[0].payload_json)
        assert payload["question"] == "Q?"

    def test_extract_candidates_strips_source_span(self) -> None:
        sr = _make_source_record()
        payloads = [{"question": "Q?", "_source_span": "s" * 300}]
        candidates = extract_candidates(sr, "faq", payloads)
        assert len(candidates[0].source_span) <= 200


# ---------------------------------------------------------------------------
# Candidate reviewer
# ---------------------------------------------------------------------------


class TestCandidateReviewer:
    def test_review_approve(self, tmp_path: Path) -> None:
        repo = ExtractionCandidateRepo(storage_dir=tmp_path)
        candidate = _make_candidate()
        repo.create(candidate)
        reviewed = review_candidate("ec-test001abc", True, reviewer="admin", candidate_repo=repo)
        assert reviewed is not None
        assert reviewed.review_status == "approved"
        assert reviewed.reviewed_by == "admin"

    def test_review_reject(self, tmp_path: Path) -> None:
        repo = ExtractionCandidateRepo(storage_dir=tmp_path)
        candidate = _make_candidate()
        repo.create(candidate)
        reviewed = review_candidate("ec-test001abc", False, reviewer="admin", candidate_repo=repo)
        assert reviewed is not None
        assert reviewed.review_status == "rejected"

    def test_publish_faq_candidate(self, tmp_path: Path) -> None:
        from app.storage.repositories.knowledge_unit_repo import KnowledgeUnit

        candidate = _make_candidate(
            payload_json=json.dumps({
                "candidate_type": "faq",
                "question": "如何请假？",
                "answer": "在系统中提交申请",
                "keywords": ["请假"],
                "business_domain": "hr",
            })
        )
        sr = _make_source_record()
        result = publish_candidate(candidate, sr)
        assert result is not None
        assert hasattr(result, "question")
        assert result.question == "如何请假？"

    def test_publish_action_link_candidate(self, tmp_path: Path) -> None:
        al_repo = ActionLinkRepo(storage_dir=tmp_path / "als")
        candidate = _make_candidate(
            candidate_type="action_link",
            payload_json=json.dumps({
                "candidate_type": "action_link",
                "label": "去请假系统",
                "url": "http://localhost:8069/odoo/time-off",
                "resource_type": "leave_form",
                "business_domains": ["hr"],
            })
        )
        sr = _make_source_record()
        result = publish_candidate(candidate, sr, action_link_repo=al_repo)
        assert result is not None
        assert result.label == "去请假系统"
        assert result.business_domains == ("hr",)

        links = al_repo.list_by_resource_type("leave_form")
        assert len(links) >= 1
        assert links[0].business_domains == ("hr",)

    def test_publish_dynamic_query_candidate(self, tmp_path: Path) -> None:
        dq_repo = DynamicQueryRepo(storage_dir=tmp_path / "dqs")
        candidate = _make_candidate(
            candidate_type="dynamic_query",
            payload_json=json.dumps({
                "candidate_type": "dynamic_query",
                "query_key": "leave_balance_test",
                "resource_type": "leave_status",
                "scope_type": "self",
                "description": "假期余额查询",
                "detect_patterns": [r"年假.{0,4}(余额|剩余)", r"剩余.{0,4}假期"],
            })
        )
        sr = _make_source_record()
        result = publish_candidate(candidate, sr, dynamic_query_repo=dq_repo)
        assert result is not None
        assert result.query_key == "leave_balance_test"
        assert result.source_record_id == "sr-test-001"
        assert result.detect_patterns == (
            r"年假.{0,4}(余额|剩余)",
            r"剩余.{0,4}假期",
        )

        dq = dq_repo.get_by_query_key("leave_balance_test")
        assert dq is not None
        assert dq.source_record_id == "sr-test-001"
        assert dq.detect_patterns == (
            r"年假.{0,4}(余额|剩余)",
            r"剩余.{0,4}假期",
        )


class _FakeExtractionProvider(ExtractionProvider):
    name = "fake"

    def complete(self, messages: list[dict[str, str]]) -> str:
        return json.dumps(
            {
                "candidates": [
                    {
                        "candidate_type": "faq",
                        "question": "如何请假？",
                        "answer": "在系统中提交申请",
                        "keywords": ["请假", "申请"],
                        "business_domain": "hr",
                    }
                ]
            }
        )


class TestExtractionService:
    def test_extract_from_record_uses_injected_provider(self, tmp_path: Path) -> None:
        from app.extract.extraction_service import ExtractionService

        repo = ExtractionCandidateRepo(storage_dir=tmp_path / "candidates")
        service = ExtractionService(candidate_repo=repo, provider=_FakeExtractionProvider())

        sr = _make_source_record(source_system="manual_export")
        candidates = service.extract_from_record(sr, candidate_types=["faq"])

        assert len(candidates) == 1
        assert candidates[0].extractor_model == "fake"
        payload = json.loads(candidates[0].payload_json)
        assert payload["question"] == "如何请假？"


# ---------------------------------------------------------------------------
# Extraction schema
# ---------------------------------------------------------------------------


class TestExtractionSchema:
    def test_extract_request(self) -> None:
        req = ExtractRequest(source_record_id="sr-001")
        assert req.candidate_types is None

    def test_extract_request_with_types(self) -> None:
        req = ExtractRequest(source_record_id="sr-001", candidate_types=["faq"])
        assert req.candidate_types == ["faq"]

    def test_review_request(self) -> None:
        req = ReviewRequest(candidate_id="ec-001", approved=True)
        assert req.reviewer is None

    def test_extract_response(self) -> None:
        resp = ExtractResponse(
            source_record_id="sr-001",
            extracted_count=0,
            candidates=[],
        )
        assert resp.extracted_count == 0

    def test_review_response(self) -> None:
        resp = ReviewResponse(
            candidate_id="ec-001",
            review_status="approved",
            reviewed_by="admin",
            reviewed_at="2025-01-01T00:00:00Z",
        )
        assert resp.published_type is None
