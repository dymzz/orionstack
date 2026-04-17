from pathlib import Path
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.indexing.elastic_indexer import ElasticIndexer, MAPPING, MAPPING_FALLBACK
from app.indexing.index_health_checker import IndexHealthChecker
from app.storage.repositories.knowledge_unit_repo import KnowledgeUnit


class _FakeIndices:
    def __init__(self) -> None:
        self.exists_value = False
        self.created = []
        self.deleted = []
        self.refreshed = []

    def exists(self, *, index: str) -> bool:
        return self.exists_value

    def create(self, *, index: str, body: dict) -> None:
        self.created.append({"index": index, "body": body})
        self.exists_value = True

    def refresh(self, *, index: str) -> None:
        self.refreshed.append(index)

    def delete(self, *, index: str) -> None:
        self.deleted.append(index)
        self.exists_value = False


class _FakeElasticsearch:
    def __init__(self) -> None:
        self.indices = _FakeIndices()
        self.indexed = []
        self.ping_value = True
        self.count_value = {"count": 0}

    def index(self, *, index: str, id: str, body: dict) -> None:
        self.indexed.append({"index": index, "id": id, "body": body})

    def ping(self) -> bool:
        return self.ping_value

    def count(self, *, index: str) -> dict:
        return self.count_value


def _build_unit(unit_id: str = "faq-001") -> KnowledgeUnit:
    return KnowledgeUnit(
        unit_id=unit_id,
        source_kind="faq",
        question="如何上传文档？",
        answer="请在文档页面点击上传按钮。",
        body_text="请在文档页面点击上传按钮。",
        keywords=("上传", "文档"),
        business_domain="hr",
        document_type="faq",
        source_type="manual_faq",
        source_label="FAQ",
        source_locator="faq-001",
        access_scope="internal",
        lifecycle_status="active",
        valid_from="2026-04-17T00:00:00Z",
        valid_until=None,
        version="v1",
        created_at="2026-04-17T00:00:00Z",
    )


def test_elastic_indexer_ensure_index_uses_fallback_mapping_by_default() -> None:
    es = _FakeElasticsearch()
    indexer = ElasticIndexer(es)

    indexer.ensure_index()

    assert es.indices.created == [{"index": "knowledge_units_v1", "body": MAPPING_FALLBACK}]


def test_elastic_indexer_ensure_index_uses_ik_mapping_when_requested() -> None:
    es = _FakeElasticsearch()
    indexer = ElasticIndexer(es)

    indexer.ensure_index(use_ik_analyzer=True)

    assert es.indices.created == [{"index": "knowledge_units_v1", "body": MAPPING}]


def test_elastic_indexer_indexes_units_and_refreshes_index() -> None:
    es = _FakeElasticsearch()
    indexer = ElasticIndexer(es)

    indexed = indexer.index_units([_build_unit("faq-001"), _build_unit("faq-002")])

    assert indexed == 2
    assert [item["id"] for item in es.indexed] == ["faq-001", "faq-002"]
    assert es.indexed[0]["body"]["unit_id"] == "faq-001"
    assert es.indices.refreshed == ["knowledge_units_v1"]


def test_index_health_checker_reports_connected_existing_index_and_count() -> None:
    es = _FakeElasticsearch()
    es.indices.exists_value = True
    es.count_value = {"count": 3}
    checker = IndexHealthChecker(es)

    result = checker.check()

    assert result == {
        "connected": True,
        "index_exists": True,
        "doc_count": 3,
        "errors": [],
    }


def test_index_health_checker_reports_connection_error() -> None:
    class _BrokenElasticsearch(_FakeElasticsearch):
        def ping(self) -> bool:
            raise RuntimeError("network down")

    checker = IndexHealthChecker(_BrokenElasticsearch())

    result = checker.check()

    assert result["connected"] is False
    assert result["index_exists"] is False
    assert result["doc_count"] == 0
    assert result["errors"] == ["Connection error: network down"]
