import pytest

from app.config.settings import Settings
from app.query.query_planner import PlannerOutput, QueryPlanner
from app.retrieval.evidence_extractor import EvidenceExtractor
from app.retrieval.hybrid_retriever import HybridHit, HybridRetriever
from app.retrieval.lexical_retriever import LexicalHit, LexicalRetriever
from app.retrieval.reranker import Reranker
from app.retrieval.vector_retriever import VectorRetriever
from app.routing.contracts import IntentDecision
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


class _FakePlanner:
    router_name = "query_planner_local"

    def __init__(self, output: PlannerOutput) -> None:
        self._output = output
        self.calls = []

    def plan(self, query: str) -> PlannerOutput:
        self.calls.append(query)
        return self._output


class _FakeHybridRetriever:
    def __init__(self, hits: list[HybridHit]) -> None:
        self._hits = hits
        self.calls = []

    def search(self, **kwargs):
        self.calls.append(kwargs)
        return list(self._hits)


def _build_hr_leave_hit() -> LexicalHit:
    return LexicalHit(
        unit_id="faq-hr-leave-001",
        source_kind="faq",
        question="如何申请年假？",
        answer="进入公司请假入口后选择假别，填写请假时间与原因并提交审批。",
        body_text="进入公司请假入口后选择假别，填写请假时间与原因并提交审批。",
        source_label="HR FAQ",
        source_locator="hr_faq_seed_v1#hr-faq-001",
        score=2.0,
        business_domain="hr",
        document_type="faq",
        source_type="manual_faq",
        access_scope="internal",
        lifecycle_status="active",
    )


def _build_hr_sick_leave_materials_hit() -> LexicalHit:
    return LexicalHit(
        unit_id="faq-hr-leave-002",
        source_kind="faq",
        question="病假需要提交什么材料？",
        answer="请在病假结束后按要求提交病假证明或医院材料，并补齐请假单据。",
        body_text="请在病假结束后按要求提交病假证明或医院材料，并补齐请假单据。",
        source_label="HR FAQ",
        source_locator="hr_faq_seed_v1#hr-faq-002",
        score=2.1,
        business_domain="hr",
        document_type="faq",
        source_type="manual_faq",
        access_scope="internal",
        lifecycle_status="active",
    )


def _build_hr_leave_progress_hit() -> LexicalHit:
    return LexicalHit(
        unit_id="faq-hr-leave-003",
        source_kind="faq",
        question="请假进度怎么看？",
        answer="进入请假记录页后可查看当前审批状态、审批节点和历史处理记录。",
        body_text="进入请假记录页后可查看当前审批状态、审批节点和历史处理记录。",
        source_label="HR FAQ",
        source_locator="hr_faq_seed_v1#hr-faq-003",
        score=2.2,
        business_domain="hr",
        document_type="faq",
        source_type="manual_faq",
        access_scope="internal",
        lifecycle_status="active",
    )


def _build_document_chunk_hit(*, score: float = 2.1) -> LexicalHit:
    return LexicalHit(
        unit_id="doc-hr-chunk-001",
        source_kind="document_chunk",
        question="",
        answer="## 4. 可入库 FAQ 内容（结构化） 下面内容可作为 FAQ 种子数据直接整理入库。",
        body_text="## 4. 可入库 FAQ 内容（结构化） 下面内容可作为 FAQ 种子数据直接整理入库。",
        source_label="domain_hr_faq_seed_v1.md",
        source_locator="document_id: doc-hr · chunk: 3",
        score=score,
        business_domain="hr",
        document_type="document",
        source_type="document_chunk",
        access_scope="internal",
        lifecycle_status="active",
    )


def _build_hybrid_leave_hit(*, score: float = 0.03) -> HybridHit:
    return HybridHit(
        unit_id="faq-hr-leave-001",
        source_kind="faq",
        question="如何申请年假？",
        answer="进入公司请假入口后选择假别，填写请假时间与原因并提交审批。",
        body_text="进入公司请假入口后选择假别，填写请假时间与原因并提交审批。",
        source_label="HR FAQ",
        source_locator="hr_faq_seed_v1#hr-faq-001",
        score=score,
        business_domain="hr",
        document_type="faq",
        source_type="manual_faq",
        access_scope="internal",
        lifecycle_status="active",
        bm25_score=2.5,
        vector_score=0.9,
        lexical_rank=1,
        vector_rank=1,
        rrf_rank=1,
    )


def _build_hybrid_document_conflict_hit(*, score: float = 0.031) -> HybridHit:
    return HybridHit(
        unit_id="doc-hr-chunk-009",
        source_kind="document_chunk",
        question="",
        answer="",
        body_text="HR FAQ 种子文档。请假属于常见问题，更多规则见 FAQ JSON 区块。",
        source_label="domain_hr_faq_seed_v1.md",
        source_locator="document_id: doc-hr · chunk: 9",
        score=score,
        business_domain="hr",
        document_type="document",
        source_type="document_chunk",
        access_scope="internal",
        lifecycle_status="active",
        bm25_score=2.6,
        vector_score=0.85,
        lexical_rank=1,
        vector_rank=2,
        rrf_rank=1,
    )


def _build_hybrid_no_evidence_hit(*, score: float = 0.028) -> HybridHit:
    return HybridHit(
        unit_id="faq-generic-001",
        source_kind="faq",
        question="如何上传文档？",
        answer="请在文档页面点击上传按钮。",
        body_text="请在文档页面点击上传按钮。",
        source_label="Docs FAQ",
        source_locator="faq-doc-001",
        score=score,
        business_domain="hr",
        document_type="faq",
        source_type="manual_faq",
        access_scope="internal",
        lifecycle_status="active",
        bm25_score=1.2,
        vector_score=0.4,
        lexical_rank=2,
        vector_rank=3,
        rrf_rank=2,
    )


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


def test_vector_retriever_scores_and_orders_candidates_from_filtered_es_docs() -> None:
    es = _CapturingElasticsearch(
        result={
            "hits": {
                "hits": [
                    {
                        "_source": {
                            "unit_id": "faq-hr-leave-001",
                            "source_kind": "faq",
                            "question": "请假申请流程是什么？",
                            "answer": "请在系统中提交请假申请并等待审批。",
                            "body_text": "请假申请 审批 流程",
                            "source_label": "HR FAQ",
                            "source_locator": "hr_faq_seed_v1#hr-faq-001",
                            "business_domain": "hr",
                            "document_type": "faq",
                            "source_type": "manual_faq",
                            "access_scope": "internal",
                            "lifecycle_status": "active",
                        }
                    },
                    {
                        "_source": {
                            "unit_id": "faq-doc-001",
                            "source_kind": "faq",
                            "question": "如何上传文档？",
                            "answer": "请点击上传按钮。",
                            "body_text": "上传 文档 页面",
                            "source_label": "Docs FAQ",
                            "source_locator": "faq-doc-001",
                            "business_domain": "hr",
                            "document_type": "faq",
                            "source_type": "manual_faq",
                            "access_scope": "internal",
                            "lifecycle_status": "active",
                        }
                    },
                ]
            }
        }
    )
    retriever = VectorRetriever(es)

    hits = retriever.search("请假审批", business_domain="hr", size=2)

    assert [hit.unit_id for hit in hits] == ["faq-hr-leave-001", "faq-doc-001"]
    assert hits[0].score > hits[1].score
    assert es.calls[0]["body"]["query"]["bool"]["filter"] == [
        {"term": {"business_domain": "hr"}},
        {"term": {"lifecycle_status": "active"}},
    ]


def test_hybrid_retriever_fuses_lexical_and_vector_hits_with_rrf() -> None:
    lexical_retriever = _FakeLexicalRetriever(
        [_build_hr_leave_hit(), _build_document_chunk_hit(score=1.5)]
    )
    vector_retriever = _FakeLexicalRetriever(
        [_build_hr_leave_hit(), _build_hr_leave_progress_hit()]
    )
    retriever = HybridRetriever(lexical_retriever, vector_retriever)

    hits = retriever.search(
        lexical_query="请假 申请 审批",
        vector_query="请假",
        lexical_terms=["请假", "审批"],
        business_domain="hr",
        size=3,
    )

    assert hits[0].unit_id == "faq-hr-leave-001"
    assert {hit.unit_id for hit in hits[1:]} == {
        "faq-hr-leave-003",
        "doc-hr-chunk-001",
    }
    assert hits[0].lexical_rank == 1
    assert hits[0].vector_rank == 1
    assert hits[0].bm25_score == 2.0
    assert hits[0].vector_score == 2.0
    assert hits[0].rrf_rank == 1
    assert lexical_retriever.calls[0]["query"] == "请假 申请 审批"
    assert vector_retriever.calls[0]["query"] == "请假"


def test_evidence_extractor_returns_ranked_span_for_leave_query() -> None:
    extractor = EvidenceExtractor()

    result = extractor.extract(
        "请假审批",
        "进入公司请假入口后选择假别。填写请假时间与原因并提交审批。",
    )

    assert result.evidence_spans
    assert "请假" in result.evidence_spans[0].text
    assert result.evidence_confidence > 0.0


def test_reranker_prefers_faq_candidate_with_evidence_over_document_chunk_conflict() -> None:
    reranker = Reranker()

    reranked_hits = reranker.rerank(
        "请假审批",
        [
            _build_hybrid_document_conflict_hit(),
            _build_hybrid_leave_hit(score=0.03),
        ],
        top_n=2,
    )

    assert reranked_hits[0].hit.unit_id == "faq-hr-leave-001"
    assert reranked_hits[0].accept is True
    assert reranked_hits[0].evidence_spans
    assert reranked_hits[0].evidence_confidence >= reranked_hits[1].evidence_confidence


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


def test_local_query_planner_outputs_minimal_fields_for_hr_leave_query() -> None:
    planner = QueryPlanner(provider="local", model="stub")

    output = planner.plan("请假")

    assert output.normalized_query == "请假"
    assert output.domain_hint == "hr"
    assert "请假" in output.lexical_terms
    assert output.planner_confidence > 0.0


def test_chat_service_uses_query_planner_outputs_in_elasticsearch_path(
    monkeypatch,
) -> None:
    fake_retriever = _FakeLexicalRetriever([_build_hr_leave_hit()])
    fake_hybrid_retriever = _FakeHybridRetriever([_build_hybrid_leave_hit()])
    fake_planner = _FakePlanner(
        PlannerOutput(
            normalized_query="请假 申请 审批",
            domain_hint="hr",
            lexical_terms=["请假", "申请", "审批"],
            planner_confidence=0.85,
        )
    )
    monkeypatch.setattr(
        chat_service_module,
        "settings",
        Settings(
            search_backend="elasticsearch",
            elastic_url="http://localhost:9200",
            enable_query_planner=True,
        ),
    )
    monkeypatch.setattr(
        ChatService,
        "_create_lexical_retriever",
        lambda self: fake_retriever,
    )
    monkeypatch.setattr(
        ChatService,
        "_create_hybrid_retriever",
        lambda self: fake_hybrid_retriever,
    )
    monkeypatch.setattr(
        ChatService,
        "_create_query_planner",
        lambda self: fake_planner,
    )

    service = ChatService()
    monkeypatch.setattr(
        service._resolver,
        "resolve",
        lambda query: (_ for _ in ()).throw(AssertionError("resolver should not run")),
    )

    response = service.ask(
        ChatAskRequest(raw_query="请假", debug=True),
        trace_id="trace-phase2-planner",
        debug_enabled=True,
    )

    assert fake_planner.calls == ["请假"]
    assert response.response_status == "ok"
    assert response.citations[0].citation_id == "faq-hr-leave-001"
    assert response.debug_info is not None
    assert response.debug_info.route_result == "faq_qa_elastic"
    assert response.debug_info.router_used == "query_planner_local"
    assert response.debug_info.retrieved_chunks == ["faq-hr-leave-001"]
    assert response.debug_info.retrieval_score == 0.03
    assert "请假" in response.citations[0].snippet
    assert fake_retriever.calls == []
    assert fake_hybrid_retriever.calls[0]["lexical_query"] == "请假 申请 审批"
    assert fake_hybrid_retriever.calls[0]["vector_query"] == "请假 申请 审批"
    assert fake_hybrid_retriever.calls[0]["business_domain"] == "hr"
    assert fake_hybrid_retriever.calls[0]["lexical_terms"] == ["请假", "申请", "审批"]


def test_chat_service_prefers_faq_evidence_over_document_chunk_in_hybrid_path(
    monkeypatch,
) -> None:
    fake_retriever = _FakeLexicalRetriever([_build_hr_leave_hit()])
    fake_hybrid_retriever = _FakeHybridRetriever(
        [
            _build_hybrid_document_conflict_hit(),
            _build_hybrid_leave_hit(score=0.03),
        ]
    )
    fake_planner = _FakePlanner(
        PlannerOutput(
            normalized_query="请假 申请 审批",
            domain_hint="hr",
            lexical_terms=["请假", "申请", "审批"],
            planner_confidence=0.85,
        )
    )
    monkeypatch.setattr(
        chat_service_module,
        "settings",
        Settings(
            search_backend="elasticsearch",
            elastic_url="http://localhost:9200",
            enable_query_planner=True,
        ),
    )
    monkeypatch.setattr(
        ChatService,
        "_create_lexical_retriever",
        lambda self: fake_retriever,
    )
    monkeypatch.setattr(
        ChatService,
        "_create_hybrid_retriever",
        lambda self: fake_hybrid_retriever,
    )
    monkeypatch.setattr(
        ChatService,
        "_create_query_planner",
        lambda self: fake_planner,
    )

    service = ChatService()
    response = service.ask(
        ChatAskRequest(raw_query="请假", debug=True),
        trace_id="trace-phase2-hybrid-rerank-faq",
        debug_enabled=True,
    )

    assert response.response_status == "ok"
    assert response.answer == "进入公司请假入口后选择假别，填写请假时间与原因并提交审批。"
    assert len(response.citations) == 1
    assert response.citations[0].citation_id == "faq-hr-leave-001"
    assert response.citations[0].source_locator == "hr_faq_seed_v1#hr-faq-001"
    assert "请假入口" in response.citations[0].snippet
    assert response.debug_info is not None
    assert response.debug_info.route_result == "faq_qa_elastic"
    assert response.debug_info.retrieved_chunks == ["faq-hr-leave-001"]
    assert response.debug_info.retrieval_score == 0.03
    assert response.debug_info.fallback_reason is None


def test_chat_service_returns_fallback_when_hybrid_hits_have_no_evidence(
    monkeypatch,
) -> None:
    fake_retriever = _FakeLexicalRetriever([_build_hr_leave_hit()])
    fake_hybrid_retriever = _FakeHybridRetriever([_build_hybrid_no_evidence_hit()])
    fake_planner = _FakePlanner(
        PlannerOutput(
            normalized_query="请假 申请 审批",
            domain_hint="hr",
            lexical_terms=["请假", "申请", "审批"],
            planner_confidence=0.85,
        )
    )
    monkeypatch.setattr(
        chat_service_module,
        "settings",
        Settings(
            search_backend="elasticsearch",
            elastic_url="http://localhost:9200",
            enable_query_planner=True,
        ),
    )
    monkeypatch.setattr(
        ChatService,
        "_create_lexical_retriever",
        lambda self: fake_retriever,
    )
    monkeypatch.setattr(
        ChatService,
        "_create_hybrid_retriever",
        lambda self: fake_hybrid_retriever,
    )
    monkeypatch.setattr(
        ChatService,
        "_create_query_planner",
        lambda self: fake_planner,
    )

    service = ChatService()
    response = service.ask(
        ChatAskRequest(raw_query="请假", debug=True),
        trace_id="trace-phase2-hybrid-no-evidence",
        debug_enabled=True,
    )

    assert response.response_status == "fallback"
    assert response.citations == []
    assert response.debug_info is not None
    assert response.debug_info.route_result == "faq_qa_elastic"
    assert response.debug_info.retrieved_chunks == []
    assert response.debug_info.retrieval_score is None
    assert response.debug_info.fallback_reason == "no_evidence"


def test_chat_service_falls_back_to_rule_parser_when_planner_confidence_is_low(
    monkeypatch,
) -> None:
    fake_retriever = _FakeLexicalRetriever([_build_hr_leave_hit()])
    fake_planner = _FakePlanner(
        PlannerOutput(
            normalized_query="请假 申请 审批",
            domain_hint="hr",
            lexical_terms=["请假", "申请", "审批"],
            planner_confidence=0.05,
        )
    )
    resolver_calls = []
    monkeypatch.setattr(
        chat_service_module,
        "settings",
        Settings(
            search_backend="elasticsearch",
            elastic_url="http://localhost:9200",
            enable_query_planner=True,
            enable_fast_track=True,
        ),
    )
    monkeypatch.setattr(
        ChatService,
        "_create_lexical_retriever",
        lambda self: fake_retriever,
    )
    monkeypatch.setattr(
        ChatService,
        "_create_query_planner",
        lambda self: fake_planner,
    )

    service = ChatService()
    monkeypatch.setattr(
        service._resolver,
        "resolve",
        lambda query: (
            resolver_calls.append(query)
            or IntentDecision(route="faq_qa", confidence=0.6, query_for_search=query)
        ),
    )

    response = service.ask(
        ChatAskRequest(raw_query="请假", debug=True),
        trace_id="trace-phase2-planner-low-confidence",
        debug_enabled=True,
    )

    assert fake_planner.calls == ["请假"]
    assert resolver_calls == ["请假"]
    assert response.response_status == "ok"
    assert response.citations[0].citation_id == "faq-hr-leave-001"
    assert response.debug_info is not None
    assert response.debug_info.router_used == "rule_parser"
    assert response.debug_info.route_result == "faq_qa_elastic"
    assert fake_retriever.calls[0]["query"] == "请假 申请 审批 流程"
    assert fake_retriever.calls[0]["business_domain"] == "hr"


@pytest.mark.parametrize(
    "raw_query, expected_search_query, expected_unit_id, expected_source_locator, hit_builder",
    [
        (
            "请假",
            "请假 申请 审批 流程",
            "faq-hr-leave-001",
            "hr_faq_seed_v1#hr-faq-001",
            _build_hr_leave_hit,
        ),
        (
            "怎么请假",
            "请假 申请 审批 流程",
            "faq-hr-leave-001",
            "hr_faq_seed_v1#hr-faq-001",
            _build_hr_leave_hit,
        ),
        (
            "如何请假",
            "请假 申请 审批 流程",
            "faq-hr-leave-001",
            "hr_faq_seed_v1#hr-faq-001",
            _build_hr_leave_hit,
        ),
        (
            "病假材料",
            "病假 证明 材料 提交",
            "faq-hr-leave-002",
            "hr_faq_seed_v1#hr-faq-002",
            _build_hr_sick_leave_materials_hit,
        ),
        (
            "请假进度怎么看",
            "请假 进度 审批 记录 查询",
            "faq-hr-leave-003",
            "hr_faq_seed_v1#hr-faq-003",
            _build_hr_leave_progress_hit,
        ),
    ],
)
def test_chat_service_phase2_elastic_regression_for_natural_leave_queries(
    monkeypatch,
    raw_query: str,
    expected_search_query: str,
    expected_unit_id: str,
    expected_source_locator: str,
    hit_builder,
) -> None:
    fake_retriever = _FakeLexicalRetriever([hit_builder()])
    monkeypatch.setattr(
        chat_service_module,
        "settings",
        Settings(
            search_backend="elasticsearch",
            elastic_url="http://localhost:9200",
            enable_fast_track=True,
        ),
    )
    monkeypatch.setattr(
        ChatService,
        "_create_lexical_retriever",
        lambda self: fake_retriever,
    )

    service = ChatService()
    monkeypatch.setattr(
        service._resolver,
        "resolve",
        lambda query: IntentDecision(
            route="faq_qa",
            confidence=0.6,
            query_for_search=query,
        ),
    )

    response = service.ask(
        ChatAskRequest(raw_query=raw_query, debug=True),
        trace_id=f"trace-phase2-natural-{raw_query}",
        debug_enabled=True,
    )

    assert response.response_status == "ok"
    assert response.answer
    assert len(response.citations) == 1
    assert response.citations[0].citation_id == expected_unit_id
    assert response.citations[0].source_label == "HR FAQ"
    assert response.citations[0].source_locator == expected_source_locator
    assert response.citations[0].snippet
    assert response.debug_info is not None
    assert response.debug_info.route_result == "faq_qa_elastic"
    assert response.debug_info.retrieved_chunks == [expected_unit_id]
    assert fake_retriever.calls[0]["query"] == expected_search_query
    assert fake_retriever.calls[0]["business_domain"] == "hr"
    assert fake_retriever.calls[0]["lifecycle_status"] == "active"
    assert fake_retriever.calls[0]["size"] == 5
    assert raw_query in fake_retriever.calls[0]["lexical_terms"]


def test_chat_service_prefers_faq_hit_over_document_chunk_in_elasticsearch_path(
    monkeypatch,
) -> None:
    fake_retriever = _FakeLexicalRetriever(
        [
            _build_document_chunk_hit(score=2.2),
            _build_hr_leave_hit(),
        ]
    )
    monkeypatch.setattr(
        chat_service_module,
        "settings",
        Settings(
            search_backend="elasticsearch",
            elastic_url="http://localhost:9200",
            enable_fast_track=True,
        ),
    )
    monkeypatch.setattr(
        ChatService,
        "_create_lexical_retriever",
        lambda self: fake_retriever,
    )

    service = ChatService()
    monkeypatch.setattr(
        service._resolver,
        "resolve",
        lambda query: IntentDecision(
            route="faq_qa",
            confidence=0.6,
            query_for_search=query,
        ),
    )

    response = service.ask(
        ChatAskRequest(raw_query="请假", debug=True),
        trace_id="trace-phase2-faq-first",
        debug_enabled=True,
    )

    assert response.response_status == "ok"
    assert response.answer == "进入公司请假入口后选择假别，填写请假时间与原因并提交审批。"
    assert len(response.citations) == 1
    assert response.citations[0].citation_id == "faq-hr-leave-001"
    assert response.citations[0].source_label == "HR FAQ"
    assert response.citations[0].source_locator == "hr_faq_seed_v1#hr-faq-001"
    assert response.debug_info is not None
    assert response.debug_info.route_result == "faq_qa_elastic"
    assert response.debug_info.retrieved_chunks == ["faq-hr-leave-001"]
    assert response.debug_info.retrieval_score == 2.0
    assert fake_retriever.calls[0]["query"] == "请假 申请 审批 流程"
    assert fake_retriever.calls[0]["business_domain"] == "hr"


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
