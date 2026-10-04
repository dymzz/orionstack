from app.storage.repositories.knowledge_unit_repo import (
    KnowledgeUnitRepository,
    map_chunk_to_knowledge_unit,
    map_faq_item_to_knowledge_unit,
)
from conftest import fixture_case


LEAVE_APPLY = fixture_case("leave_apply")
LEAVE_PROGRESS = fixture_case("leave_progress")


class _StaticRepo:
    def __init__(self, items):
        self._items = items

    def list_all(self):
        return list(self._items)


def test_map_faq_item_to_knowledge_unit_applies_defaults() -> None:
    unit = map_faq_item_to_knowledge_unit(
        {
            "id": "faq-001",
            "question": "如何上传文档？",
            "answer": "请在文档页面点击上传按钮。",
            "keywords": ["上传", "文档"],
            "created_at": "2026-04-17T00:00:00Z",
        }
    )

    assert unit.unit_id == "faq-001"
    assert unit.source_kind == "faq"
    assert unit.question == "如何上传文档？"
    assert unit.answer == "请在文档页面点击上传按钮。"
    assert unit.body_text == "请在文档页面点击上传按钮。"
    assert unit.keywords == ("上传", "文档")
    assert unit.business_domain == "hr"
    assert unit.document_type == "faq"
    assert unit.source_type == "manual_faq"
    assert unit.source_label == "FAQ"
    assert unit.source_locator == "faq-001"
    assert unit.access_scope == "internal"
    assert unit.lifecycle_status == "active"
    assert unit.valid_until is None
    assert unit.version == "v1"


def test_map_faq_item_to_knowledge_unit_preserves_provenance_fields() -> None:
    unit = map_faq_item_to_knowledge_unit(
        {
            "id": "faq-001",
            "question": "如何请假？",
            "answer": "在系统中提交申请。",
            "keywords": ["请假"],
            "source_record_id": "sr-001",
            "import_batch_id": "ib-001",
            "unit_version": 2,
            "source_updated_at": "2026-05-01T00:00:00Z",
            "fresh_until": "2026-06-01T00:00:00Z",
            "stale_after": "2026-07-01T00:00:00Z",
        }
    )

    assert unit.source_record_id == "sr-001"
    assert unit.import_batch_id == "ib-001"
    assert unit.unit_version == 2
    assert unit.source_updated_at == "2026-05-01T00:00:00Z"
    assert unit.fresh_until == "2026-06-01T00:00:00Z"
    assert unit.stale_after == "2026-07-01T00:00:00Z"


def test_map_chunk_to_knowledge_unit_preserves_chunk_locator() -> None:
    unit = map_chunk_to_knowledge_unit(
        {
            "chunk_id": "doc-001-chunk-1",
            "text": "预算审批规则位于预算制度说明第二节。",
            "source_label": "budget_guide.txt",
            "source_locator": "document_id: doc-001 · chunk: 1",
            "created_at": "2026-04-17T00:00:00Z",
        }
    )

    assert unit.unit_id == "doc-001-chunk-1"
    assert unit.source_kind == "document_chunk"
    assert unit.question == ""
    assert unit.answer == "预算审批规则位于预算制度说明第二节。"
    assert unit.body_text == "预算审批规则位于预算制度说明第二节。"
    assert unit.document_type == "document"
    assert unit.source_type == "document_chunk"
    assert unit.source_label == "budget_guide.txt"
    assert unit.source_locator == "document_id: doc-001 · chunk: 1"
    assert unit.access_scope == "internal"
    assert unit.lifecycle_status == "active"
    assert unit.valid_until is None
    assert unit.version == "v1"


def test_map_chunk_to_knowledge_unit_preserves_provenance_fields() -> None:
    unit = map_chunk_to_knowledge_unit(
        {
            "chunk_id": "doc-001-chunk-1",
            "text": "预算审批规则位于预算制度说明第二节。",
            "source_record_id": "sr-doc-001",
            "import_batch_id": "ib-doc-001",
            "unit_version": 3,
            "source_updated_at": "2026-05-02T00:00:00Z",
        }
    )

    assert unit.source_record_id == "sr-doc-001"
    assert unit.import_batch_id == "ib-doc-001"
    assert unit.unit_version == 3
    assert unit.source_updated_at == "2026-05-02T00:00:00Z"


def test_knowledge_unit_repository_lists_faq_and_chunk_units_in_single_view() -> None:
    repository = KnowledgeUnitRepository(
        faq_repo=_StaticRepo(
            [
                {
                    "id": "faq-001",
                    "question": "如何上传文档？",
                    "answer": "请在文档页面点击上传按钮。",
                }
            ]
        ),
        chunk_repo=_StaticRepo(
            [
                {
                    "chunk_id": "doc-001-chunk-1",
                    "text": "预算审批规则位于预算制度说明第二节。",
                    "source_label": "budget_guide.txt",
                    "source_locator": "document_id: doc-001 · chunk: 1",
                }
            ]
        ),
    )

    units = repository.list_all()
    faq_units = repository.list_faq_units()
    chunk_units = repository.list_chunk_units()

    assert units[0].unit_id == "faq-001"
    assert units[-1].unit_id == "doc-001-chunk-1"
    assert units[0].source_kind == "faq"
    assert units[-1].source_kind == "document_chunk"
    assert "faq-001" in [unit.unit_id for unit in faq_units]
    assert [unit.unit_id for unit in faq_units] == ["faq-001"]
    assert [unit.unit_id for unit in chunk_units] == ["doc-001-chunk-1"]


def test_knowledge_unit_repository_preserves_explicit_fixture_provenance() -> None:
    repository = KnowledgeUnitRepository(faq_repo=_StaticRepo([LEAVE_APPLY, LEAVE_PROGRESS]))

    faq_units = repository.list_faq_units()

    leave_unit = next(unit for unit in faq_units if unit.unit_id == LEAVE_APPLY["id"])
    progress_unit = next(unit for unit in faq_units if unit.unit_id == LEAVE_PROGRESS["id"])

    assert leave_unit.source_kind == "faq"
    assert leave_unit.question == LEAVE_APPLY["question"]
    assert leave_unit.answer.startswith(LEAVE_APPLY["answer"][:8])
    assert leave_unit.source_label == LEAVE_APPLY["source_label"]
    assert leave_unit.source_locator == LEAVE_APPLY["source_locator"]
    assert leave_unit.business_domain == "hr"
    assert "请假" in leave_unit.keywords

    assert progress_unit.source_locator == LEAVE_PROGRESS["source_locator"]
    assert "审批" in progress_unit.keywords
