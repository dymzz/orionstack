import json

import pytest
from fastapi.testclient import TestClient

from app.api.routes import chat as chat_route
from app.api.routes import extraction as extraction_route
from app.extract.candidate_reviewer import publish_candidate
from app.schemas.request import ChatAskRequest
from app.services.chat_service import ChatService
from app.storage.repositories.extracted_faq_repo import ExtractedFaqRepo
from app.storage.repositories.knowledge_unit_repo import KnowledgeUnitRepository
from test_extraction import _make_candidate, _make_source_record
from main import app


def test_published_faqs_survive_reload_and_are_answered_locally(tmp_path):
    repo = ExtractedFaqRepo()
    source = _make_source_record()
    published = []
    for candidate_id, question, answer in (
        ("ec-roundtrip-001", "如何申请星际补贴？", "在航天门户填写星际补贴申请。"),
        ("ec-roundtrip-002", "如何提交量子维修？", "在量子门户提交维修工单。"),
    ):
        candidate = _make_candidate(
            candidate_id=candidate_id,
            payload_json=json.dumps({"question": question, "answer": answer}),
            review_status="approved",
        )
        published.append(publish_candidate(candidate, source, extracted_faq_repo=repo))

    reloaded = ExtractedFaqRepo(storage_dir=repo._dir)
    knowledge = KnowledgeUnitRepository(extracted_faq_repo=reloaded)
    knowledge._seed_dir = tmp_path / "empty-seed"
    knowledge._upload_dir = tmp_path / "empty-uploads"
    assert {unit.unit_id for unit in knowledge.list_all()} == {
        unit.unit_id for unit in published
    }
    assert all(unit.source_record_id == source.source_record_id for unit in knowledge.list_all())

    service = ChatService()
    response = service.ask(
        ChatAskRequest(raw_query="如何申请星际补贴？"),
        trace_id="publication-roundtrip",
        debug_enabled=False,
    )
    assert response.response_status == "ok"
    assert response.answer == published[0].answer
    assert response.citations[0].citation_id == published[0].unit_id

    updated = reloaded.update_status_by_source_record(source.source_record_id, "revoked")
    assert set(updated) == {unit.unit_id for unit in published}
    assert all(item["lifecycle_status"] == "revoked" for item in reloaded.list_all())
    assert service._retriever.search("星际补贴", min_score=1) is None


def test_extracted_faq_upsert_accepts_legacy_id_and_updates_canonical_id(tmp_path):
    repo = ExtractedFaqRepo(storage_dir=tmp_path)
    legacy = {"id": "legacy-faq", "question": "Legacy?", "answer": "Before"}
    repo._file.write_text(json.dumps(legacy) + "\n", encoding="utf-8")
    repo.upsert({"unit_id": "legacy-faq", "question": "Legacy?", "answer": "After"})
    knowledge = KnowledgeUnitRepository(extracted_faq_repo=repo)
    knowledge._seed_dir = tmp_path / "empty-seed"
    knowledge._upload_dir = tmp_path / "empty-uploads"
    units = knowledge.list_all()
    assert len(units) == 1
    assert units[0].unit_id == "legacy-faq"
    assert units[0].answer == "After"


def test_reviewed_faq_is_available_through_chat_after_service_reload(monkeypatch, admin_headers):
    source = _make_source_record()
    candidate = _make_candidate(
        candidate_id="ec-api-reload",
        payload_json=json.dumps({
            "question": "如何申请星际津贴？",
            "answer": "在星际门户提交津贴申请。",
        }),
    )
    extraction_route._source_record_repo.upsert(source)
    extraction_route._candidate_repo.create(candidate)
    client = TestClient(app)
    reviewed = client.post(
        "/api/v1/extraction/review",
        json={"candidate_id": candidate.candidate_id, "approved": True},
        headers=admin_headers,
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["published_type"] == "KnowledgeUnit"

    # Construct a new service so the HTTP path must use the persisted publication.
    monkeypatch.setattr(chat_route, "service", ChatService())
    response = client.post(
        "/api/v1/chat/ask",
        json={"raw_query": "如何申请星际津贴？", "debug": True},
        headers=admin_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["response_status"] == "ok"
    assert body["answer"] == "在星际门户提交津贴申请。"
    assert body["citations"][0]["citation_id"] == extraction_route._extracted_faq_repo.list_all()[0]["unit_id"]
    assert body["debug_info"]["source_record_id"] == source.source_record_id


def test_extracted_faq_requires_an_identifier(tmp_path):
    repo = ExtractedFaqRepo(storage_dir=tmp_path)
    with pytest.raises(ValueError, match="unit_id"):
        repo.upsert({"question": "Missing?", "answer": "No identifier"})
    assert repo.list_all() == []


def test_legacy_duplicate_publications_keep_the_latest_version(tmp_path):
    repo = ExtractedFaqRepo(storage_dir=tmp_path)
    items = [
        {"unit_id": "repeated", "question": "Question", "answer": "Old"},
        {"id": "repeated", "question": "Question", "answer": "Current"},
    ]
    repo._file.write_text("\n".join(json.dumps(item) for item in items) + "\n", encoding="utf-8")
    assert len(repo.list_all()) == 1
    assert repo.list_all()[0]["answer"] == "Current"
