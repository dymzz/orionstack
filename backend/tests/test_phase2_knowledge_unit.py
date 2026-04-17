from pathlib import Path
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.storage.repositories.knowledge_unit_repo import (
    KnowledgeUnitRepository,
    map_chunk_to_knowledge_unit,
    map_faq_item_to_knowledge_unit,
)


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

    assert [unit.unit_id for unit in units] == ["faq-001", "doc-001-chunk-1"]
    assert [unit.source_kind for unit in units] == ["faq", "document_chunk"]
    assert [unit.unit_id for unit in faq_units] == ["faq-001"]
    assert [unit.unit_id for unit in chunk_units] == ["doc-001-chunk-1"]
