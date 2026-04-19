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

    assert units[0].unit_id == "faq-001"
    assert units[-1].unit_id == "doc-001-chunk-1"
    assert units[0].source_kind == "faq"
    assert units[-1].source_kind == "document_chunk"
    assert "faq-001" in [unit.unit_id for unit in faq_units]
    assert "hr-faq-001" in [unit.unit_id for unit in faq_units]
    assert [unit.unit_id for unit in chunk_units] == ["doc-001-chunk-1"]


def test_knowledge_unit_repository_loads_hr_seed_markdown_faq_units() -> None:
    repository = KnowledgeUnitRepository()

    faq_units = repository.list_faq_units()

    leave_unit = next(unit for unit in faq_units if unit.unit_id == "hr-faq-001")
    progress_unit = next(unit for unit in faq_units if unit.unit_id == "hr-faq-003")

    assert leave_unit.source_kind == "faq"
    assert leave_unit.question == "如何申请年假？"
    assert leave_unit.answer.startswith("进入公司请假入口后选择年假")
    assert leave_unit.source_label == "HR FAQ"
    assert leave_unit.source_locator == "hr_faq_seed_v1#hr-faq-001"
    assert leave_unit.business_domain == "hr"
    assert "请假" in leave_unit.keywords

    assert progress_unit.source_locator == "hr_faq_seed_v1#hr-faq-003"
    assert "审批" in progress_unit.keywords
