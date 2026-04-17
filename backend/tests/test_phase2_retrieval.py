from pathlib import Path
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.config.settings import Settings
from app.retrieval.lexical_retriever import LexicalHit, LexicalRetriever
from app.schemas.request import ChatAskRequest
from app.services import chat_service as chat_service_module
from app.services.chat_service import ChatService


class _CapturingElasticsearch:
    def __init__(self, *, result: dict | None = None, error: Exception | None = None) -> None:
        self.result = result or {"hits": {"hits": []}}
        self.error = error
        self.calls = []

    def search(self, *, index: str, body: dict) -> dict:
        self.calls.append({"index": index, "body": body})
        if self.error is not None:
            raise self.error
        return self.result


class _FakeLexicalRetriever:
    def __init__(self, hits: list[LexicalHit]) -> None:
        self._hits = hits
        self.calls = []

    def search(self, query: str, **kwargs):
        self.calls.append({"query": query, **kwargs})
        return list(self._hits)


def test_lexical_retriever_returns_empty_for_blank_query() -> None:
    es = _CapturingElasticsearch()
    retriever = LexicalRetriever(es)

    hits = retriever.search("   ")

    assert hits == []
    assert es.calls == []


def test_lexical_retriever_builds_expected_filters_and_maps_hits() -> None:
    es = _CapturingElasticsearch(
        result={
            "hits": {
                "hits": [
                    {
                        "_score": 2.5,
                        "_source": {
                            "unit_id": "faq-001",
                            "source_kind": "faq",
                            "question": "如何上传文档？",
                            "answer": "请在文档页面点击上传按钮。",
                            "body_text": "请在文档页面点击上传按钮。",
                            "source_label": "Mock FAQ",
                            "source_locator": "faq-001",
                            "business_domain": "hr",
                            "document_type": "faq",
                            "source_type": "manual_faq",
                            "access_scope": "internal",
                            "lifecycle_status": "active",
                        },
                    }
                ]
            }
        }
    )
    retriever = LexicalRetriever(es)

    hits = retriever.search(
        "请假",
        lexical_terms=["请假", "病假"],
        business_domain="hr",
        access_scope="internal",
        size=3,
    )

    assert len(hits) == 1
    assert hits[0].unit_id == "faq-001"
    assert hits[0].score == 2.5
    assert len(es.calls) == 1
    request_body = es.calls[0]["body"]
    assert es.calls[0]["index"] == "knowledge_units_v1"
    assert request_body["size"] == 3
    assert request_body["min_score"] == 0.1
    assert request_body["query"]["bool"]["filter"] == [
        {"term": {"business_domain": "hr"}},
        {"term": {"access_scope": "internal"}},
        {"term": {"lifecycle_status": "active"}},
    ]
    assert request_body["query"]["bool"]["should"] == [
        {"term": {"keywords": "请假"}},
        {"term": {"keywords": "病假"}},
    ]


def test_lexical_retriever_returns_empty_when_search_raises() -> None:
    es = _CapturingElasticsearch(error=RuntimeError("search failed"))
    retriever = LexicalRetriever(es)

    hits = retriever.search("请假")

    assert hits == []
    assert len(es.calls) == 1


def test_chat_service_uses_elasticsearch_backend_when_configured(monkeypatch) -> None:
    fake_retriever = _FakeLexicalRetriever(
        [
            LexicalHit(
                unit_id="faq-001",
                source_kind="faq",
                question="如何上传文档？",
                answer="请在文档页面点击上传按钮。",
                body_text="请在文档页面点击上传按钮。",
                source_label="Mock FAQ",
                source_locator="faq-001",
                score=2.0,
                business_domain="hr",
                document_type="faq",
                source_type="manual_faq",
                access_scope="internal",
                lifecycle_status="active",
            )
        ]
    )
    monkeypatch.setattr(
        chat_service_module,
        "settings",
        Settings(search_backend="elasticsearch", elastic_url="http://localhost:9200"),
    )
    monkeypatch.setattr(
        ChatService,
        "_create_lexical_retriever",
        lambda self: fake_retriever,
    )

    service = ChatService()
    response = service.ask(
        ChatAskRequest(raw_query="如何上传文档？", debug=True),
        trace_id="trace-phase2-elastic",
        debug_enabled=True,
    )

    assert response.response_status == "ok"
    assert response.answer == "请在文档页面点击上传按钮。"
    assert len(response.citations) == 1
    assert response.citations[0].citation_id == "faq-001"
    assert response.debug_info is not None
    assert response.debug_info.route_result == "faq_qa_elastic"
    assert response.debug_info.retrieved_chunks == ["faq-001"]
    assert fake_retriever.calls[0]["query"] == "如何上传文档？"
    assert fake_retriever.calls[0]["lifecycle_status"] == "active"
    assert fake_retriever.calls[0]["size"] == 5


def test_chat_service_returns_fallback_when_elasticsearch_backend_has_no_hits(
    monkeypatch,
) -> None:
    fake_retriever = _FakeLexicalRetriever([])
    monkeypatch.setattr(
        chat_service_module,
        "settings",
        Settings(search_backend="elasticsearch", elastic_url="http://localhost:9200"),
    )
    monkeypatch.setattr(
        ChatService,
        "_create_lexical_retriever",
        lambda self: fake_retriever,
    )

    service = ChatService()
    response = service.ask(
        ChatAskRequest(raw_query="如何上传文档？", debug=True),
        trace_id="trace-phase2-elastic-no-hit",
        debug_enabled=True,
    )

    assert response.response_status == "fallback"
    assert response.citations == []
    assert response.debug_info is not None
    assert response.debug_info.route_result == "faq_qa_elastic"
    assert response.debug_info.fallback_reason == "retrieval_no_hit"
    assert fake_retriever.calls[0]["query"] == "如何上传文档？"


def test_chat_service_extracts_lexical_terms_with_query_bigrams_and_trigrams() -> None:
    terms = ChatService._extract_lexical_terms("如何申请年假")

    assert terms[0] == "如何申请年假"
    assert "如何" in terms
    assert "申请" in terms
    assert "年假" in terms
    assert "如何申" in terms
    assert "申请年" in terms
    assert len(terms) == len(set(terms))
