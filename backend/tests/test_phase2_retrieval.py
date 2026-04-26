import pytest

from app.config.settings import Settings
from app.query.query_planner import PlannerOutput, QueryPlanner
from app.retrieval.evidence_extractor import EvidenceExtractor
from app.retrieval.hybrid_retriever import HybridHit, HybridRetriever
from app.retrieval.lexical_retriever import (
    LexicalHit,
    LexicalRetriever,
    RetrievalBackendError,
)
from app.retrieval.reranker import Reranker
from app.retrieval.vector_retriever import VectorRetriever
from app.routing.contracts import IntentDecision
from app.schemas.request import ChatAskRequest
from app.services import chat_service as chat_service_module
from app.services.chat_service import ChatService
from conftest import fixture_case, fixture_faq_map, fixture_path_for_faq_id


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


class _FailingRetriever:
    def __init__(self, error: RetrievalBackendError) -> None:
        self._error = error
        self.calls = []

    def search(self, query: str, **kwargs):
        self.calls.append({"query": query, **kwargs})
        raise self._error


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


def _build_local_planner_output(query: str) -> PlannerOutput:
    return QueryPlanner(provider="local", model="stub").plan(query)


LEAVE_APPLY = fixture_case("leave_apply")
SICK_LEAVE_MATERIALS = fixture_case("sick_leave_materials")
LEAVE_PROGRESS = fixture_case("leave_progress")
ATTENDANCE_APPEAL = fixture_case("attendance_appeal")
ONBOARDING_DAY_ONE = fixture_case("onboarding_day_one")
EMPLOYMENT_CERTIFICATE = fixture_case("employment_certificate")
BENEFITS_INFO = fixture_case("benefits_info")
TIMEOFF_BALANCE = fixture_case("timeoff_balance")

LEAVE_APPLY_ID = LEAVE_APPLY["id"]
SICK_LEAVE_MATERIALS_ID = SICK_LEAVE_MATERIALS["id"]
LEAVE_PROGRESS_ID = LEAVE_PROGRESS["id"]
ATTENDANCE_APPEAL_ID = ATTENDANCE_APPEAL["id"]
ONBOARDING_DAY_ONE_ID = ONBOARDING_DAY_ONE["id"]
EMPLOYMENT_CERTIFICATE_ID = EMPLOYMENT_CERTIFICATE["id"]
BENEFITS_INFO_ID = BENEFITS_INFO["id"]
TIMEOFF_BALANCE_ID = TIMEOFF_BALANCE["id"]

LEAVE_APPLY_LOCATOR = LEAVE_APPLY["source_locator"]
SICK_LEAVE_MATERIALS_LOCATOR = SICK_LEAVE_MATERIALS["source_locator"]
LEAVE_PROGRESS_LOCATOR = LEAVE_PROGRESS["source_locator"]
ATTENDANCE_APPEAL_LOCATOR = ATTENDANCE_APPEAL["source_locator"]
ONBOARDING_DAY_ONE_LOCATOR = ONBOARDING_DAY_ONE["source_locator"]
TIMEOFF_BALANCE_LOCATOR = TIMEOFF_BALANCE["source_locator"]
LEAVE_APPLY_FIXTURE_NAME = fixture_path_for_faq_id(LEAVE_APPLY_ID).name


def _build_fixture_lexical_hit(item: dict, *, score: float) -> LexicalHit:
    return LexicalHit(
        unit_id=item["id"],
        source_kind="faq",
        question=item["question"],
        answer=item["answer"],
        body_text=item["answer"],
        source_label=item["source_label"],
        source_locator=item["source_locator"],
        score=score,
        business_domain=item["business_domain"],
        document_type=item["document_type"],
        source_type=item["source_type"],
        access_scope=item["access_scope"],
        lifecycle_status=item["lifecycle_status"],
    )


def _build_fixture_hybrid_hit(
    item: dict,
    *,
    score: float,
    lexical_rank: int,
    vector_rank: int,
    rrf_rank: int,
    bm25_score: float = 2.0,
    vector_score: float = 0.5,
) -> HybridHit:
    return HybridHit(
        unit_id=item["id"],
        source_kind="faq",
        question=item["question"],
        answer=item["answer"],
        body_text=item["answer"],
        source_label=item["source_label"],
        source_locator=item["source_locator"],
        score=score,
        business_domain=item["business_domain"],
        document_type=item["document_type"],
        source_type=item["source_type"],
        access_scope=item["access_scope"],
        lifecycle_status=item["lifecycle_status"],
        bm25_score=bm25_score,
        vector_score=vector_score,
        lexical_rank=lexical_rank,
        vector_rank=vector_rank,
        rrf_rank=rrf_rank,
    )


def _build_hr_leave_hit() -> LexicalHit:
    return _build_fixture_lexical_hit(LEAVE_APPLY, score=2.0)


def _build_hr_sick_leave_materials_hit() -> LexicalHit:
    return _build_fixture_lexical_hit(SICK_LEAVE_MATERIALS, score=2.1)


def _build_hr_leave_progress_hit() -> LexicalHit:
    return _build_fixture_lexical_hit(LEAVE_PROGRESS, score=2.2)


def _build_document_chunk_hit(*, score: float = 2.1) -> LexicalHit:
    return LexicalHit(
        unit_id="doc-hr-chunk-001",
        source_kind="document_chunk",
        question="",
        answer="## 4. 可入库 FAQ 内容（结构化） 下面内容可作为 FAQ 种子数据直接整理入库。",
        body_text="## 4. 可入库 FAQ 内容（结构化） 下面内容可作为 FAQ 种子数据直接整理入库。",
        source_label=LEAVE_APPLY_FIXTURE_NAME,
        source_locator="document_id: doc-hr · chunk: 3",
        score=score,
        business_domain="hr",
        document_type="document",
        source_type="document_chunk",
        access_scope="internal",
        lifecycle_status="active",
    )


def _build_hybrid_leave_hit(*, score: float = 0.03) -> HybridHit:
    return _build_fixture_hybrid_hit(
        LEAVE_APPLY,
        score=score,
        lexical_rank=1,
        vector_rank=1,
        rrf_rank=1,
        bm25_score=2.5,
        vector_score=0.9,
    )


def _build_hybrid_sick_leave_materials_hit(*, score: float = 0.030478) -> HybridHit:
    return _build_fixture_hybrid_hit(
        SICK_LEAVE_MATERIALS,
        score=score,
        lexical_rank=5,
        vector_rank=4,
        rrf_rank=5,
    )


def _build_hybrid_leave_progress_hit(*, score: float = 0.031778) -> HybridHit:
    return _build_fixture_hybrid_hit(
        LEAVE_PROGRESS,
        score=score,
        lexical_rank=2,
        vector_rank=2,
        rrf_rank=2,
        bm25_score=2.3,
        vector_score=0.85,
    )


def _build_hybrid_leave_process_hit(*, score: float = 0.032258) -> HybridHit:
    return _build_fixture_hybrid_hit(
        LEAVE_APPLY,
        score=score,
        lexical_rank=1,
        vector_rank=1,
        rrf_rank=1,
        bm25_score=2.4,
        vector_score=0.88,
    )


def _build_hybrid_sick_leave_process_hit(*, score: float = 0.0319) -> HybridHit:
    return _build_fixture_hybrid_hit(
        ATTENDANCE_APPEAL,
        score=score,
        lexical_rank=2,
        vector_rank=2,
        rrf_rank=2,
        bm25_score=2.2,
        vector_score=0.86,
    )


def _build_hybrid_onboarding_first_day_hit(*, score: float = 0.0316) -> HybridHit:
    return _build_fixture_hybrid_hit(
        ONBOARDING_DAY_ONE,
        score=score,
        lexical_rank=3,
        vector_rank=3,
        rrf_rank=3,
        bm25_score=2.1,
        vector_score=0.84,
    )


def _build_hybrid_generic_fixture_hit(
    case_name: str,
    *,
    score: float,
    lexical_rank: int,
    vector_rank: int,
    rrf_rank: int,
    bm25_score: float = 2.0,
    vector_score: float = 0.5,
) -> HybridHit:
    return _build_fixture_hybrid_hit(
        fixture_case(case_name),
        score=score,
        lexical_rank=lexical_rank,
        vector_rank=vector_rank,
        rrf_rank=rrf_rank,
        bm25_score=bm25_score,
        vector_score=vector_score,
    )


def _build_hybrid_document_conflict_hit(*, score: float = 0.031) -> HybridHit:
    return HybridHit(
        unit_id="doc-hr-chunk-009",
        source_kind="document_chunk",
        question="",
        answer="",
        body_text="FAQ 种子文档。请假属于常见问题，更多规则见 FAQ JSON 区块。",
        source_label=LEAVE_APPLY_FIXTURE_NAME,
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


def _build_hybrid_fixture_hit(
    faq_id: str,
    *,
    score: float,
    lexical_rank: int,
    vector_rank: int,
    rrf_rank: int,
    bm25_score: float = 2.0,
    vector_score: float = 0.5,
) -> HybridHit:
    return _build_fixture_hybrid_hit(
        fixture_faq_map()[faq_id],
        score=score,
        bm25_score=bm25_score,
        vector_score=vector_score,
        lexical_rank=lexical_rank,
        vector_rank=vector_rank,
        rrf_rank=rrf_rank,
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
                            "source_record_id": "sr-001",
                            "import_batch_id": "ib-001",
                            "unit_version": 2,
                            "fresh_until": "2026-06-01T00:00:00Z",
                            "stale_after": "2026-07-01T00:00:00Z",
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
    assert hits[0].source_record_id == "sr-001"
    assert hits[0].import_batch_id == "ib-001"
    assert hits[0].unit_version == 2
    assert hits[0].fresh_until == "2026-06-01T00:00:00Z"
    assert hits[0].stale_after == "2026-07-01T00:00:00Z"
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


def test_lexical_retriever_raises_backend_error_when_search_raises() -> None:
    es = _CapturingElasticsearch(error=RuntimeError("search failed"))
    retriever = LexicalRetriever(es)

    with pytest.raises(RetrievalBackendError) as error:
        retriever.search("请假")

    assert error.value.stage == "lexical"
    assert error.value.cause_name == "RuntimeError"
    assert len(es.calls) == 1


def test_chat_service_returns_backend_error_fallback_when_elasticsearch_search_raises(
    monkeypatch,
) -> None:
    class _FailingLexicalRetriever:
        def search(self, query: str, **kwargs):
            raise RetrievalBackendError("lexical", RuntimeError("search failed"))

    monkeypatch.setattr(
        chat_service_module,
        "settings",
        Settings(search_backend="elasticsearch", elastic_url="http://localhost:9200"),
    )
    monkeypatch.setattr(
        ChatService,
        "_create_lexical_retriever",
        lambda self: _FailingLexicalRetriever(),
    )

    service = ChatService()
    response = service.ask(
        ChatAskRequest(raw_query="如何上传文档？", debug=True),
        trace_id="trace-phase2-elastic-backend-error",
        debug_enabled=True,
    )

    assert response.response_status == "fallback"
    assert response.citations == []
    assert response.debug_info is not None
    assert response.debug_info.route_result == "faq_qa_elastic"
    assert response.debug_info.fallback_reason == "lexical_backend_error"
    assert response.debug_info.retrieval_mode == "lexical_only"
    assert response.debug_info.reject_reason == "RuntimeError"


def test_vector_retriever_scores_and_orders_candidates_from_filtered_es_docs() -> None:
    es = _CapturingElasticsearch(
        result={
            "hits": {
                "hits": [
                    {
                        "_source": {
                            "unit_id": LEAVE_APPLY_ID,
                            "source_kind": "faq",
                            "question": "请假申请流程是什么？",
                            "answer": "请在系统中提交请假申请并等待审批。",
                            "body_text": "请假申请 审批 流程",
                            "source_label": LEAVE_APPLY["source_label"],
                            "source_locator": LEAVE_APPLY_LOCATOR,
                            "business_domain": "hr",
                            "document_type": "faq",
                            "source_type": "manual_faq",
                            "access_scope": "internal",
                            "lifecycle_status": "active",
                            "source_record_id": "sr-leave-001",
                            "import_batch_id": "ib-leave-001",
                            "unit_version": 4,
                            "fresh_until": "2026-06-01T00:00:00Z",
                            "stale_after": "2026-07-01T00:00:00Z",
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

    assert [hit.unit_id for hit in hits] == [LEAVE_APPLY_ID, "faq-doc-001"]
    assert hits[0].score > hits[1].score
    assert hits[0].source_record_id == "sr-leave-001"
    assert hits[0].import_batch_id == "ib-leave-001"
    assert hits[0].unit_version == 4
    assert hits[0].fresh_until == "2026-06-01T00:00:00Z"
    assert hits[0].stale_after == "2026-07-01T00:00:00Z"
    assert es.calls[0]["body"]["query"]["bool"]["filter"] == [
        {"term": {"business_domain": "hr"}},
        {"term": {"lifecycle_status": "active"}},
    ]


def test_hybrid_retriever_preserves_vector_only_provenance() -> None:
    vector_hit = LexicalHit(
        unit_id="unit-vector-only",
        source_kind="faq",
        question="如何请假？",
        answer="在系统中提交申请。",
        body_text="在系统中提交申请。",
        source_label="HR FAQ",
        source_locator="hr#leave",
        score=0.8,
        business_domain="hr",
        document_type="faq",
        source_type="manual_faq",
        access_scope="internal",
        lifecycle_status="active",
        source_record_id="sr-vector-001",
        import_batch_id="ib-vector-001",
        unit_version=5,
        fresh_until="2026-06-01T00:00:00Z",
        stale_after="2026-07-01T00:00:00Z",
    )
    retriever = HybridRetriever(
        _FakeLexicalRetriever([]),
        _FakeLexicalRetriever([vector_hit]),
    )

    hits = retriever.search(
        lexical_query="请假",
        vector_query="请假",
        business_domain="hr",
        size=3,
    )

    assert len(hits) == 1
    assert hits[0].source_record_id == "sr-vector-001"
    assert hits[0].import_batch_id == "ib-vector-001"
    assert hits[0].unit_version == 5
    assert hits[0].fresh_until == "2026-06-01T00:00:00Z"
    assert hits[0].stale_after == "2026-07-01T00:00:00Z"


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

    assert hits[0].unit_id == LEAVE_APPLY_ID
    assert {hit.unit_id for hit in hits[1:]} == {
        LEAVE_PROGRESS_ID,
        "doc-hr-chunk-001",
    }
    assert hits[0].lexical_rank == 1
    assert hits[0].vector_rank == 1
    assert hits[0].bm25_score == 2.0
    assert hits[0].vector_score == 2.0
    assert hits[0].rrf_rank == 1
    assert lexical_retriever.calls[0]["query"] == "请假 申请 审批"
    assert vector_retriever.calls[0]["query"] == "请假"


def test_hybrid_retriever_soft_fallbacks_to_vector_when_lexical_backend_fails() -> None:
    lexical_error = RetrievalBackendError("lexical", RuntimeError("search failed"))
    lexical_retriever = _FailingRetriever(lexical_error)
    vector_retriever = _FakeLexicalRetriever([_build_hr_leave_hit()])
    retriever = HybridRetriever(lexical_retriever, vector_retriever)

    hits = retriever.search(
        lexical_query="请假 申请",
        vector_query="请假",
        lexical_terms=["请假"],
        business_domain="hr",
        size=3,
    )

    assert [hit.unit_id for hit in hits] == [LEAVE_APPLY_ID]
    assert hits[0].lexical_rank is None
    assert hits[0].vector_rank == 1
    assert hits[0].bm25_score is None
    assert hits[0].vector_score == 2.0
    assert retriever.last_backend_warning is not None
    assert retriever.last_backend_warning.failed_stage == "lexical"
    assert retriever.last_backend_warning.cause_name == "RuntimeError"
    assert retriever.last_backend_warning.fallback_stage == "vector"


def test_hybrid_retriever_raises_backend_error_when_both_branches_fail() -> None:
    lexical_retriever = _FailingRetriever(
        RetrievalBackendError("lexical", RuntimeError("lexical failed"))
    )
    vector_retriever = _FailingRetriever(
        RetrievalBackendError("vector", RuntimeError("vector failed"))
    )
    retriever = HybridRetriever(lexical_retriever, vector_retriever)

    with pytest.raises(RetrievalBackendError) as error:
        retriever.search(
            lexical_query="请假",
            vector_query="请假",
            lexical_terms=["请假"],
            size=3,
        )

    assert error.value.stage == "lexical"
    assert retriever.last_backend_warning is None


def test_hybrid_retriever_keeps_dominant_lexical_faq_ahead_of_noisy_vector_hits() -> None:
    lexical_retriever = _FakeLexicalRetriever(
        [
            _build_fixture_lexical_hit(LEAVE_APPLY, score=49.93),
            _build_fixture_lexical_hit(LEAVE_PROGRESS, score=10.14),
            _build_fixture_lexical_hit(ATTENDANCE_APPEAL, score=9.96),
            _build_fixture_lexical_hit(ONBOARDING_DAY_ONE, score=9.49),
        ]
    )
    vector_retriever = _FakeLexicalRetriever(
        [
            _build_fixture_lexical_hit(ATTENDANCE_APPEAL, score=0.317),
            _build_fixture_lexical_hit(ONBOARDING_DAY_ONE, score=0.285),
            _build_fixture_lexical_hit(LEAVE_PROGRESS, score=0.231),
        ]
    )
    retriever = HybridRetriever(lexical_retriever, vector_retriever)

    hits = retriever.search(
        lexical_query="通用泛问法",
        vector_query="通用泛问法",
        lexical_terms=["通用泛问法", "通用", "泛问", "问法"],
        lifecycle_status="active",
        size=5,
    )

    assert hits[0].unit_id == LEAVE_APPLY_ID
    assert hits[0].lexical_rank == 1
    assert hits[0].vector_rank is None
    assert hits[0].score > hits[1].score


def test_hybrid_retriever_keeps_domain_diverse_candidates_when_unscoped() -> None:
    faq_by_id = fixture_faq_map()
    lexical_retriever = _FakeLexicalRetriever(
        [
            _build_fixture_lexical_hit(faq_by_id["finance-faq-001"], score=5.0),
            _build_fixture_lexical_hit(faq_by_id["hr-faq-001"], score=4.9),
            _build_fixture_lexical_hit(faq_by_id["admin-faq-001"], score=4.8),
            _build_fixture_lexical_hit(faq_by_id["hr-faq-002"], score=4.7),
            _build_fixture_lexical_hit(faq_by_id["sales-faq-003"], score=4.6),
        ]
    )
    vector_retriever = _FakeLexicalRetriever([])
    retriever = HybridRetriever(lexical_retriever, vector_retriever)

    hits = retriever.search(
        lexical_query="资料在哪里找",
        vector_query="资料在哪里找",
        lexical_terms=["资料", "哪里"],
        lifecycle_status="active",
        size=4,
    )

    assert [hit.unit_id for hit in hits] == [
        "finance-faq-001",
        "hr-faq-001",
        "admin-faq-001",
        "sales-faq-003",
    ]


def test_hybrid_retriever_keeps_dominant_lexical_document_chunk_ahead_of_noisy_vector_hits() -> None:
    # Without the generic lexical-winner protection, a strong document-chunk
    # lexical winner (rank 1, no vector rank) would lose RRF to a both-list
    # noisy candidate because the old FAQ-only rule did not grant the dominance
    # bonus to document_chunk units.
    lexical_retriever = _FakeLexicalRetriever(
        [
            _build_document_chunk_hit(score=49.93),
            _build_fixture_lexical_hit(LEAVE_PROGRESS, score=10.14),
            _build_fixture_lexical_hit(ATTENDANCE_APPEAL, score=9.96),
            _build_fixture_lexical_hit(ONBOARDING_DAY_ONE, score=9.49),
        ]
    )
    vector_retriever = _FakeLexicalRetriever(
        [
            _build_fixture_lexical_hit(ATTENDANCE_APPEAL, score=0.317),
            _build_fixture_lexical_hit(ONBOARDING_DAY_ONE, score=0.285),
            _build_fixture_lexical_hit(LEAVE_PROGRESS, score=0.231),
        ]
    )
    retriever = HybridRetriever(lexical_retriever, vector_retriever)

    hits = retriever.search(
        lexical_query="通用泛问法",
        vector_query="通用泛问法",
        lifecycle_status="active",
        size=5,
    )

    assert hits[0].unit_id == "doc-hr-chunk-001"
    assert hits[0].source_kind == "document_chunk"
    assert hits[0].lexical_rank == 1
    assert hits[0].vector_rank is None
    assert hits[0].score > hits[1].score


def test_hybrid_retriever_keeps_dominant_lexical_winner_when_runner_up_is_different_source_kind() -> None:
    # Top lexical hit is a FAQ but the runner-up is a document chunk, so the
    # old FAQ-only rule could see at most one FAQ and would refuse to protect
    # the winner. The generic rule compares top vs next regardless of kind.
    lexical_retriever = _FakeLexicalRetriever(
        [
            _build_fixture_lexical_hit(LEAVE_APPLY, score=49.93),
            _build_document_chunk_hit(score=10.14),
            _build_fixture_lexical_hit(ATTENDANCE_APPEAL, score=9.96),
        ]
    )
    vector_retriever = _FakeLexicalRetriever(
        [
            _build_fixture_lexical_hit(ATTENDANCE_APPEAL, score=0.317),
            _build_document_chunk_hit(score=0.285),
        ]
    )
    retriever = HybridRetriever(lexical_retriever, vector_retriever)

    hits = retriever.search(
        lexical_query="通用泛问法",
        vector_query="通用泛问法",
        lifecycle_status="active",
        size=5,
    )

    assert hits[0].unit_id == LEAVE_APPLY_ID
    assert hits[0].lexical_rank == 1
    assert hits[0].vector_rank is None
    assert hits[0].score > hits[1].score


def test_hybrid_retriever_protects_lonely_strong_lexical_winner() -> None:
    # Lexical list has a single meaningful hit (well above the absolute floor).
    # The old FAQ-only, len>=2 rule returned None and granted no bonus. The
    # generic rule allows a lonely strong lexical hit to still be marked as
    # the dominant winner so it stays ahead when fusion is later tightened.
    lexical_retriever = _FakeLexicalRetriever(
        [_build_fixture_lexical_hit(LEAVE_APPLY, score=7.5)]
    )
    vector_retriever = _FakeLexicalRetriever(
        [
            _build_fixture_lexical_hit(ATTENDANCE_APPEAL, score=0.317),
            _build_fixture_lexical_hit(ONBOARDING_DAY_ONE, score=0.285),
        ]
    )
    retriever = HybridRetriever(lexical_retriever, vector_retriever)

    hits = retriever.search(
        lexical_query="请假入口",
        vector_query="请假入口",
        lifecycle_status="active",
        size=5,
    )

    assert hits[0].unit_id == LEAVE_APPLY_ID
    assert hits[0].lexical_rank == 1
    assert hits[0].vector_rank is None


def test_hybrid_retriever_does_not_find_dominant_lexical_winner_below_absolute_floor() -> None:
    # A single weak lexical hit below the absolute floor must not receive the
    # dominance bonus, so a rare-term fluke cannot override a symmetric
    # bothlist noisy rival in future fusion-tightening work.
    from app.retrieval.hybrid_retriever import HybridRetriever as _HybridRetrieverCls

    weak_only = [_build_fixture_lexical_hit(LEAVE_APPLY, score=0.3)]

    dominant_id = _HybridRetrieverCls._find_dominant_lexical_winner_id(weak_only)

    assert dominant_id is None


def test_hybrid_retriever_keeps_dominant_vector_winner_ahead_of_noisy_lexical_hits() -> None:
    # Symmetric case: vector top-1 is clearly dominant (0.85 vs 0.20 runner-up),
    # but a noisy candidate appears in both lists (lexical rank 3 + vector rank 2)
    # and would otherwise out-RRF the lexical-absent vector winner. The generic
    # vector-side dominance bonus must protect the true winner.
    lexical_retriever = _FakeLexicalRetriever(
        [
            _build_fixture_lexical_hit(ATTENDANCE_APPEAL, score=2.5),
            _build_fixture_lexical_hit(ONBOARDING_DAY_ONE, score=2.3),
            _build_fixture_lexical_hit(LEAVE_PROGRESS, score=2.0),
        ]
    )
    vector_retriever = _FakeLexicalRetriever(
        [
            _build_fixture_lexical_hit(LEAVE_APPLY, score=0.85),
            _build_fixture_lexical_hit(LEAVE_PROGRESS, score=0.20),
        ]
    )
    retriever = HybridRetriever(lexical_retriever, vector_retriever)

    hits = retriever.search(
        lexical_query="通用泛问法",
        vector_query="通用泛问法",
        lifecycle_status="active",
        size=5,
    )

    assert hits[0].unit_id == LEAVE_APPLY_ID
    assert hits[0].vector_rank == 1
    assert hits[0].lexical_rank is None
    assert hits[0].score > hits[1].score


def test_hybrid_retriever_protects_lonely_strong_vector_winner() -> None:
    # Vector list has a single meaningful hit (well above the vector floor).
    # The symmetric lonely-winner path grants the dominance bonus so the winner
    # stays ahead of any vector-only noise or bothlist rivals in later fusion
    # tightening.
    lexical_retriever = _FakeLexicalRetriever(
        [
            _build_fixture_lexical_hit(ATTENDANCE_APPEAL, score=2.5),
            _build_fixture_lexical_hit(ONBOARDING_DAY_ONE, score=2.3),
        ]
    )
    vector_retriever = _FakeLexicalRetriever(
        [_build_fixture_lexical_hit(LEAVE_APPLY, score=0.82)]
    )
    retriever = HybridRetriever(lexical_retriever, vector_retriever)

    hits = retriever.search(
        lexical_query="请假流程",
        vector_query="请假流程",
        lifecycle_status="active",
        size=5,
    )

    assert hits[0].unit_id == LEAVE_APPLY_ID
    assert hits[0].vector_rank == 1
    assert hits[0].lexical_rank is None


def test_hybrid_retriever_records_dominance_attribution_per_candidate_on_hybrid_hits() -> None:
    # Observability: the fusion layer must tag each HybridHit with which side
    # (if any) granted it the dominance bonus. Required for future trace
    # replay so a reviewer can tell apart a bonus-assisted winner from a
    # plain RRF winner without rerunning retrieval. Attribution must be
    # per-candidate, not a global flag.
    lexical_retriever = _FakeLexicalRetriever(
        [
            _build_fixture_lexical_hit(LEAVE_APPLY, score=49.93),
            _build_fixture_lexical_hit(LEAVE_PROGRESS, score=10.14),
            _build_fixture_lexical_hit(ATTENDANCE_APPEAL, score=9.96),
        ]
    )
    vector_retriever = _FakeLexicalRetriever(
        [
            _build_fixture_lexical_hit(ATTENDANCE_APPEAL, score=0.317),
            _build_fixture_lexical_hit(LEAVE_PROGRESS, score=0.285),
        ]
    )
    retriever = HybridRetriever(lexical_retriever, vector_retriever)

    hits = retriever.search(
        lexical_query="通用泛问法",
        vector_query="通用泛问法",
        lifecycle_status="active",
        size=5,
    )

    hits_by_id = {hit.unit_id: hit for hit in hits}

    assert hits[0].unit_id == LEAVE_APPLY_ID
    assert hits_by_id[LEAVE_APPLY_ID].lexical_dominance_applied is True
    assert hits_by_id[LEAVE_APPLY_ID].vector_dominance_applied is False
    assert hits_by_id[LEAVE_PROGRESS_ID].lexical_dominance_applied is False
    assert hits_by_id[LEAVE_PROGRESS_ID].vector_dominance_applied is False
    assert hits_by_id[ATTENDANCE_APPEAL_ID].lexical_dominance_applied is False
    # Vector top (0.317) is below the 0.5 vector floor — no vector dominance
    # should fire for any candidate in this scenario.
    assert all(hit.vector_dominance_applied is False for hit in hits)


def test_hybrid_retriever_does_not_find_dominant_vector_winner_below_absolute_floor() -> None:
    # A single weak vector hit below the vector absolute floor must not
    # receive the dominance bonus; otherwise a low-similarity fluke would
    # override meaningful lexical matches.
    from app.retrieval.hybrid_retriever import HybridRetriever as _HybridRetrieverCls

    weak_only = [_build_fixture_lexical_hit(LEAVE_APPLY, score=0.3)]

    dominant_id = _HybridRetrieverCls._find_dominant_vector_winner_id(weak_only)

    assert dominant_id is None


def test_chat_service_propagates_lexical_dominance_bonus_through_rerank_to_response(
    monkeypatch,
) -> None:
    # End-to-end proof that the fusion-layer lexical dominance bonus survives
    # rerank + evidence + response building. Without the bonus, the both-list
    # noisy ATTENDANCE_APPEAL candidate would out-RRF the lexical-only
    # LEAVE_APPLY winner (0.0323 vs 0.0164), enter rerank at rank 1, score
    # poorly on "如何申请年假" evidence, and trigger a no_evidence fallback.
    # With the bonus (0.0164 + 0.02 = 0.0364), LEAVE_APPLY stays at fusion
    # rank 1, carries high evidence_confidence through rerank, and becomes the
    # user-visible answer.
    from app.retrieval.hybrid_retriever import HybridRetriever as _RealHybridRetriever

    fake_lexical_retriever = _FakeLexicalRetriever(
        [
            _build_fixture_lexical_hit(LEAVE_APPLY, score=49.93),
            _build_fixture_lexical_hit(LEAVE_PROGRESS, score=10.14),
            _build_fixture_lexical_hit(ATTENDANCE_APPEAL, score=9.96),
            _build_fixture_lexical_hit(ONBOARDING_DAY_ONE, score=9.49),
        ]
    )
    fake_vector_retriever = _FakeLexicalRetriever(
        [
            _build_fixture_lexical_hit(ATTENDANCE_APPEAL, score=0.317),
            _build_fixture_lexical_hit(ONBOARDING_DAY_ONE, score=0.285),
            _build_fixture_lexical_hit(LEAVE_PROGRESS, score=0.231),
        ]
    )
    real_hybrid = _RealHybridRetriever(fake_lexical_retriever, fake_vector_retriever)
    fake_planner = _FakePlanner(
        PlannerOutput(
            normalized_query="如何申请年假",
            domain_hint=None,
            lexical_terms=["如何申请年假", "申请", "年假", "请假"],
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
        lambda self: fake_lexical_retriever,
    )
    monkeypatch.setattr(
        ChatService,
        "_create_hybrid_retriever",
        lambda self: real_hybrid,
    )
    monkeypatch.setattr(
        ChatService,
        "_create_query_planner",
        lambda self: fake_planner,
    )

    service = ChatService()
    response = service.ask(
        ChatAskRequest(raw_query="如何申请年假", debug=True),
        trace_id="trace-fusion-bonus-e2e",
        debug_enabled=True,
    )

    assert response.response_status == "ok"
    assert response.citations
    assert response.citations[0].citation_id == LEAVE_APPLY_ID
    assert response.answer == LEAVE_APPLY["answer"]
    assert response.debug_info is not None
    assert response.debug_info.retrieval_mode == "hybrid_rerank"
    assert response.debug_info.rerank_accept is True
    assert response.debug_info.retrieved_chunks == [LEAVE_APPLY_ID]
    assert response.debug_info.rrf_topk is not None
    assert response.debug_info.rrf_topk[0].unit_id == LEAVE_APPLY_ID


def test_chat_service_propagates_vector_dominance_bonus_through_rerank_to_response(
    monkeypatch,
) -> None:
    # Symmetric end-to-end proof for the vector-side dominance bonus. The true
    # winner LEAVE_APPLY is only present on the vector side (rank 1, score well
    # above the vector floor 0.5). A noisy both-list rival LEAVE_PROGRESS would
    # out-RRF it (L3 + V2 = 0.0320) and push LEAVE_APPLY out of the rerank
    # top_n window, triggering a no_evidence fallback. The vector dominance
    # bonus (+0.02) restores LEAVE_APPLY to fusion rank 1 and keeps the
    # rerank/evidence chain capable of producing the correct answer.
    from app.retrieval.hybrid_retriever import HybridRetriever as _RealHybridRetriever

    fake_lexical_retriever = _FakeLexicalRetriever(
        [
            _build_fixture_lexical_hit(ATTENDANCE_APPEAL, score=2.5),
            _build_fixture_lexical_hit(ONBOARDING_DAY_ONE, score=2.3),
            _build_fixture_lexical_hit(LEAVE_PROGRESS, score=2.0),
        ]
    )
    fake_vector_retriever = _FakeLexicalRetriever(
        [
            _build_fixture_lexical_hit(LEAVE_APPLY, score=0.85),
            _build_fixture_lexical_hit(LEAVE_PROGRESS, score=0.20),
        ]
    )
    real_hybrid = _RealHybridRetriever(fake_lexical_retriever, fake_vector_retriever)
    fake_planner = _FakePlanner(
        PlannerOutput(
            normalized_query="如何申请年假",
            domain_hint=None,
            lexical_terms=["如何申请年假", "申请", "年假", "请假"],
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
        lambda self: fake_lexical_retriever,
    )
    monkeypatch.setattr(
        ChatService,
        "_create_hybrid_retriever",
        lambda self: real_hybrid,
    )
    monkeypatch.setattr(
        ChatService,
        "_create_query_planner",
        lambda self: fake_planner,
    )

    service = ChatService()
    response = service.ask(
        ChatAskRequest(raw_query="如何申请年假", debug=True),
        trace_id="trace-fusion-vector-bonus-e2e",
        debug_enabled=True,
    )

    assert response.response_status == "ok"
    assert response.citations
    assert response.citations[0].citation_id == LEAVE_APPLY_ID
    assert response.answer == LEAVE_APPLY["answer"]
    assert response.debug_info is not None
    assert response.debug_info.retrieval_mode == "hybrid_rerank"
    assert response.debug_info.rerank_accept is True
    assert response.debug_info.retrieved_chunks == [LEAVE_APPLY_ID]
    assert response.debug_info.rrf_topk is not None
    assert response.debug_info.rrf_topk[0].unit_id == LEAVE_APPLY_ID


def test_chat_service_surfaces_fusion_dominance_attribution_in_debug_rrf_topk(
    monkeypatch,
) -> None:
    # Observability end-to-end: the per-candidate dominance attribution set
    # inside _fuse_hits must survive both the rrf_rank re-sort and the
    # RetrievalCandidateSummary projection, so downstream trace viewers see
    # exactly which candidate in rrf_topk earned a bonus. Same fusion
    # scenario as the lexical e2e test, now asserting the attribution fields
    # are populated in debug_info (and, via model_dump in chat.py, in the
    # persisted retrieval_trace JSONL).
    from app.retrieval.hybrid_retriever import HybridRetriever as _RealHybridRetriever

    fake_lexical_retriever = _FakeLexicalRetriever(
        [
            _build_fixture_lexical_hit(LEAVE_APPLY, score=49.93),
            _build_fixture_lexical_hit(LEAVE_PROGRESS, score=10.14),
            _build_fixture_lexical_hit(ATTENDANCE_APPEAL, score=9.96),
            _build_fixture_lexical_hit(ONBOARDING_DAY_ONE, score=9.49),
        ]
    )
    fake_vector_retriever = _FakeLexicalRetriever(
        [
            _build_fixture_lexical_hit(ATTENDANCE_APPEAL, score=0.317),
            _build_fixture_lexical_hit(ONBOARDING_DAY_ONE, score=0.285),
            _build_fixture_lexical_hit(LEAVE_PROGRESS, score=0.231),
        ]
    )
    real_hybrid = _RealHybridRetriever(fake_lexical_retriever, fake_vector_retriever)
    fake_planner = _FakePlanner(
        PlannerOutput(
            normalized_query="如何申请年假",
            domain_hint=None,
            lexical_terms=["如何申请年假", "申请", "年假", "请假"],
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
        lambda self: fake_lexical_retriever,
    )
    monkeypatch.setattr(
        ChatService,
        "_create_hybrid_retriever",
        lambda self: real_hybrid,
    )
    monkeypatch.setattr(
        ChatService,
        "_create_query_planner",
        lambda self: fake_planner,
    )

    service = ChatService()
    response = service.ask(
        ChatAskRequest(raw_query="如何申请年假", debug=True),
        trace_id="trace-fusion-dominance-attribution",
        debug_enabled=True,
    )

    assert response.debug_info is not None
    assert response.debug_info.rrf_topk is not None

    rrf_by_id = {item.unit_id: item for item in response.debug_info.rrf_topk}

    # Bonus-assisted winner surfaces with lexical_dominance_applied True.
    assert response.debug_info.rrf_topk[0].unit_id == LEAVE_APPLY_ID
    assert rrf_by_id[LEAVE_APPLY_ID].lexical_dominance_applied is True
    assert rrf_by_id[LEAVE_APPLY_ID].vector_dominance_applied is False

    # The noisy both-list rival that would have won without the bonus must
    # not be mis-attributed: its lexical_dominance_applied must be False.
    assert ATTENDANCE_APPEAL_ID in rrf_by_id
    assert rrf_by_id[ATTENDANCE_APPEAL_ID].lexical_dominance_applied is False
    assert rrf_by_id[ATTENDANCE_APPEAL_ID].vector_dominance_applied is False


def test_chat_service_propagates_planner_domain_hint_to_both_lexical_and_vector_sides(
    monkeypatch,
) -> None:
    # Regression guard on the planner.domain_hint data flow:
    #   planner.domain_hint
    #     -> ChatService.business_domain
    #     -> HybridRetriever.search(business_domain=...)
    #     -> Lexical.search(business_domain=...)   [ES filter]
    #     -> Vector.search(business_domain=...)    [ES filter]
    #
    # All four links already exist in source, but no existing test asserts
    # a non-None domain_hint actually narrows both sides. A future refactor
    # that drops the kwarg on either side would silently widen retrieval
    # and reintroduce cross-domain noise that fusion bonus cannot fully
    # absorb. This test uses a real HybridRetriever wrapping fake retrievers
    # so it can read back the business_domain kwarg on both legs.
    from app.retrieval.hybrid_retriever import HybridRetriever as _RealHybridRetriever

    leave_apply_hit = _build_fixture_lexical_hit(LEAVE_APPLY, score=2.0)
    fake_lexical_retriever = _FakeLexicalRetriever([leave_apply_hit])
    fake_vector_retriever = _FakeLexicalRetriever([leave_apply_hit])
    real_hybrid = _RealHybridRetriever(fake_lexical_retriever, fake_vector_retriever)
    fake_planner = _FakePlanner(
        PlannerOutput(
            normalized_query="如何申请年假",
            domain_hint="hr",
            lexical_terms=["如何申请年假", "申请", "年假"],
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
        lambda self: fake_lexical_retriever,
    )
    monkeypatch.setattr(
        ChatService,
        "_create_hybrid_retriever",
        lambda self: real_hybrid,
    )
    monkeypatch.setattr(
        ChatService,
        "_create_query_planner",
        lambda self: fake_planner,
    )

    service = ChatService()
    response = service.ask(
        ChatAskRequest(raw_query="如何申请年假", debug=True),
        trace_id="trace-domain-hint-propagation",
        debug_enabled=True,
    )

    assert response.response_status == "ok"
    assert response.debug_info is not None
    assert response.debug_info.domain_hint == "hr"
    assert fake_lexical_retriever.calls
    assert fake_vector_retriever.calls
    assert fake_lexical_retriever.calls[0]["business_domain"] == "hr"
    assert fake_vector_retriever.calls[0]["business_domain"] == "hr"


def test_evidence_extractor_returns_ranked_span_for_leave_query() -> None:
    extractor = EvidenceExtractor()

    result = extractor.extract(
        "请假审批",
        "进入公司请假入口后选择假别。填写请假时间与原因并提交审批。",
    )

    assert result.evidence_spans
    assert "请假" in result.evidence_spans[0].text
    assert result.evidence_confidence > 0.0


def test_evidence_extractor_ignores_generic_question_words_for_irrelevant_text() -> None:
    extractor = EvidenceExtractor()

    result = extractor.extract(
        "什么叫请假",
        "入职第一天需要办理什么手续？",
    )

    assert result.evidence_spans == []
    assert result.evidence_confidence == 0.0


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

    assert reranked_hits[0].hit.unit_id == LEAVE_APPLY_ID
    assert reranked_hits[0].accept is True
    assert reranked_hits[0].evidence_spans
    assert reranked_hits[0].evidence_confidence >= reranked_hits[1].evidence_confidence


def test_reranker_accepts_exact_faq_question_match_using_question_and_answer() -> None:
    reranker = Reranker()

    reranked_hits = reranker.rerank(
        "如何申请年假？",
        [_build_hybrid_leave_process_hit()],
        top_n=1,
    )

    assert len(reranked_hits) == 1
    assert reranked_hits[0].hit.unit_id == LEAVE_APPLY_ID
    assert reranked_hits[0].accept is True
    assert reranked_hits[0].evidence_spans
    assert "如何申请年假" in reranked_hits[0].evidence_spans[0].text


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
    assert response.debug_info.retrieval_mode == "lexical_only"
    assert fake_retriever.calls[0]["query"] == "如何上传文档？"
    assert fake_retriever.calls[0]["lifecycle_status"] == "active"
    assert fake_retriever.calls[0]["size"] == 5


def test_local_query_planner_outputs_minimal_fields_for_non_empty_query() -> None:
    planner = QueryPlanner(provider="local", model="stub")

    output = planner.plan("请假")

    assert output.normalized_query == "请假"
    assert output.domain_hint is None
    assert "请假" in output.lexical_terms
    assert output.planner_confidence > 0.0


def test_chat_service_uses_query_planner_outputs_in_elasticsearch_path(
    monkeypatch,
) -> None:
    fake_retriever = _FakeLexicalRetriever([_build_hr_leave_hit()])
    fake_hybrid_retriever = _FakeHybridRetriever([_build_hybrid_leave_hit()])
    fake_planner = _FakePlanner(
        PlannerOutput(
            normalized_query="请假",
            domain_hint=None,
            lexical_terms=["请假"],
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
    assert response.citations[0].citation_id == LEAVE_APPLY_ID
    assert response.debug_info is not None
    assert response.debug_info.route_result == "faq_qa_elastic"
    assert response.debug_info.router_used == "query_planner_local"
    assert response.debug_info.retrieved_chunks == [LEAVE_APPLY_ID]
    assert response.debug_info.retrieval_score is None
    assert response.debug_info.fusion_score == 0.03
    assert response.debug_info.retrieval_mode == "hybrid_rerank"
    assert response.debug_info.lexical_topk is not None
    assert [item.unit_id for item in response.debug_info.lexical_topk] == [
        LEAVE_APPLY_ID
    ]
    assert response.debug_info.vector_topk is not None
    assert [item.unit_id for item in response.debug_info.vector_topk] == [
        LEAVE_APPLY_ID
    ]
    assert response.debug_info.rrf_topk is not None
    assert [item.unit_id for item in response.debug_info.rrf_topk] == [
        LEAVE_APPLY_ID
    ]
    assert response.debug_info.rerank_accept is True
    assert response.debug_info.rerank_score is not None
    assert response.debug_info.evidence_confidence is not None
    assert response.debug_info.evidence_confidence > 0.15
    assert response.debug_info.evidence_span_count is not None
    assert response.debug_info.evidence_span_count >= 1
    assert response.debug_info.reject_reason is None
    assert "请假" in response.citations[0].snippet
    assert fake_retriever.calls == []
    assert fake_hybrid_retriever.calls[0]["lexical_query"] == "请假"
    assert fake_hybrid_retriever.calls[0]["vector_query"] == "请假"
    assert fake_hybrid_retriever.calls[0]["business_domain"] is None
    assert fake_hybrid_retriever.calls[0]["lexical_terms"] == ["请假"]


def test_chat_service_augments_unscoped_planner_terms_before_hybrid_search(
    monkeypatch,
) -> None:
    sales_hit = _build_hybrid_fixture_hit(
        "sales-faq-003",
        score=0.031,
        lexical_rank=4,
        vector_rank=5,
        rrf_rank=4,
        bm25_score=2.2,
        vector_score=0.62,
    )
    fake_retriever = _FakeLexicalRetriever([])
    fake_hybrid_retriever = _FakeHybridRetriever([sales_hit])
    fake_planner = _FakePlanner(
        PlannerOutput(
            normalized_query="演示资料在哪里找",
            domain_hint=None,
            lexical_terms=["演示资料"],
            planner_confidence=0.86,
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
        ChatAskRequest(raw_query="演示资料在哪里找", debug=True),
        trace_id="trace-phase2-unscoped-term-guard",
        debug_enabled=True,
    )

    assert response.response_status == "ok"
    assert response.citations[0].citation_id == "sales-faq-003"
    assert fake_hybrid_retriever.calls[0]["size"] == ChatService._UNSCOPED_HYBRID_RERANK_SIZE
    effective_terms = fake_hybrid_retriever.calls[0]["lexical_terms"]
    assert effective_terms[0] == "演示资料"
    assert "演示" in effective_terms
    assert "资料" in effective_terms


def test_chat_service_uses_hybrid_soft_fallback_when_lexical_branch_times_out(
    monkeypatch,
) -> None:
    fake_retriever = _FakeLexicalRetriever([_build_hr_leave_hit()])
    soft_fallback_hybrid = HybridRetriever(
        _FailingRetriever(
            RetrievalBackendError("lexical", RuntimeError("search timed out"))
        ),
        _FakeLexicalRetriever([_build_hr_leave_hit()]),
    )
    fake_planner = _FakePlanner(
        PlannerOutput(
            normalized_query="如何申请年假",
            domain_hint="hr",
            lexical_terms=["申请年假", "年假"],
            planner_confidence=0.9,
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
        lambda self: soft_fallback_hybrid,
    )
    monkeypatch.setattr(
        ChatService,
        "_create_query_planner",
        lambda self: fake_planner,
    )

    service = ChatService()
    response = service.ask(
        ChatAskRequest(raw_query="如何申请年假", debug=True),
        trace_id="trace-phase2-hybrid-soft-fallback",
        debug_enabled=True,
    )

    assert response.response_status == "ok"
    assert response.citations[0].citation_id == LEAVE_APPLY_ID
    assert response.debug_info is not None
    assert response.debug_info.fallback_reason == "lexical_backend_soft_fallback"
    assert (
        response.debug_info.reject_reason
        == "lexical_backend_soft_fallback:RuntimeError"
    )
    assert response.debug_info.retrieval_mode == "hybrid_rerank"
    assert response.debug_info.lexical_topk == []
    assert response.debug_info.vector_topk is not None
    assert [item.unit_id for item in response.debug_info.vector_topk] == [
        LEAVE_APPLY_ID
    ]
    assert response.debug_info.rrf_topk is not None
    assert [item.unit_id for item in response.debug_info.rrf_topk] == [
        LEAVE_APPLY_ID
    ]


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
            normalized_query="请假",
            domain_hint=None,
            lexical_terms=["请假"],
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
    assert response.answer == LEAVE_APPLY["answer"]
    assert len(response.citations) == 1
    assert response.citations[0].citation_id == LEAVE_APPLY_ID
    assert response.citations[0].source_locator == LEAVE_APPLY_LOCATOR
    assert "请假入口" in response.citations[0].snippet
    assert response.debug_info is not None
    assert response.debug_info.route_result == "faq_qa_elastic"
    assert response.debug_info.retrieved_chunks == [LEAVE_APPLY_ID]
    assert response.debug_info.retrieval_score is None
    assert response.debug_info.fusion_score == 0.03
    assert response.debug_info.fallback_reason is None
    assert response.debug_info.retrieval_mode == "hybrid_rerank"
    assert response.clarification is None


def test_chat_service_returns_clarification_for_close_faq_candidates_in_hybrid_path(
    monkeypatch,
) -> None:
    fake_retriever = _FakeLexicalRetriever([_build_hr_leave_hit()])
    fake_hybrid_retriever = _FakeHybridRetriever(
        [
            _build_hybrid_leave_process_hit(score=0.032258),
            _build_hybrid_leave_progress_hit(score=0.0319),
            _build_hybrid_generic_fixture_hit(
                "benefits_info",
                score=0.028,
                lexical_rank=3,
                vector_rank=3,
                rrf_rank=3,
            ),
        ]
    )
    fake_planner = _FakePlanner(
        _build_local_planner_output("请假")
    )
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
        trace_id="trace-phase2-hybrid-clarification",
        debug_enabled=True,
    )

    assert response.response_status == "ok"
    assert response.clarification is not None
    assert response.clarification.clarification_required is True
    assert response.clarification.question == "您更想了解以下哪一项？"
    assert response.clarification.conflict_reason == "multiple_close_faq_candidates"
    assert [option.option_id for option in response.clarification.options] == [
        LEAVE_APPLY_ID,
        LEAVE_PROGRESS_ID,
    ]
    assert [option.label for option in response.clarification.options] == [
        LEAVE_APPLY["question"],
        LEAVE_PROGRESS["question"],
    ]
    assert len(response.citations) == 2
    assert response.citations[0].citation_id == LEAVE_APPLY_ID
    assert response.citations[1].citation_id == LEAVE_PROGRESS_ID
    assert response.debug_info is not None
    assert response.debug_info.route_result == "faq_qa_elastic"
    assert response.debug_info.fallback_reason == "conflict_requires_clarification"
    assert response.debug_info.retrieved_chunks == [LEAVE_APPLY_ID, LEAVE_PROGRESS_ID]
    assert response.debug_info.domain_hint is None
    assert response.debug_info.lexical_terms == _build_local_planner_output("请假").lexical_terms
    assert response.debug_info.planner_confidence == 0.88
    assert response.debug_info.retrieval_mode == "clarification"
    assert response.debug_info.retrieval_score is None
    assert response.debug_info.fusion_score == 0.032258
    assert response.debug_info.lexical_topk is not None
    assert [item.unit_id for item in response.debug_info.lexical_topk] == [
        LEAVE_APPLY_ID,
        LEAVE_PROGRESS_ID,
        BENEFITS_INFO_ID,
    ]
    assert response.debug_info.vector_topk is not None
    assert [item.unit_id for item in response.debug_info.vector_topk] == [
        LEAVE_APPLY_ID,
        LEAVE_PROGRESS_ID,
        BENEFITS_INFO_ID,
    ]
    assert response.debug_info.rrf_topk is not None
    assert [item.unit_id for item in response.debug_info.rrf_topk] == [
        LEAVE_APPLY_ID,
        LEAVE_PROGRESS_ID,
        BENEFITS_INFO_ID,
    ]
    assert response.debug_info.rerank_accept is True
    assert response.debug_info.rerank_score is not None
    assert response.debug_info.evidence_confidence is not None
    assert response.debug_info.evidence_confidence > 0.15
    assert response.debug_info.evidence_span_count is not None
    assert response.debug_info.evidence_span_count >= 1
    assert response.debug_info.reject_reason == "multiple_close_faq_candidates"


def test_chat_service_excludes_irrelevant_candidate_from_clarification_options(
    monkeypatch,
) -> None:
    fake_retriever = _FakeLexicalRetriever([_build_hr_leave_hit()])
    fake_hybrid_retriever = _FakeHybridRetriever(
        [
            _build_hybrid_leave_process_hit(score=0.032258),
            _build_hybrid_leave_progress_hit(score=0.0319),
            _build_hybrid_onboarding_first_day_hit(score=0.0316),
        ]
    )
    fake_planner = _FakePlanner(
        _build_local_planner_output("什么叫请假")
    )
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
        ChatAskRequest(raw_query="什么叫请假", debug=True),
        trace_id="trace-phase2-hybrid-clarification-filter",
        debug_enabled=True,
    )

    assert response.response_status == "ok"
    assert response.clarification is not None
    assert [option.option_id for option in response.clarification.options] == [
        LEAVE_APPLY_ID,
        LEAVE_PROGRESS_ID,
    ]
    assert [option.label for option in response.clarification.options] == [
        LEAVE_APPLY["question"],
        LEAVE_PROGRESS["question"],
    ]
    assert ONBOARDING_DAY_ONE_ID not in [citation.citation_id for citation in response.citations]
    assert response.debug_info is not None
    assert response.debug_info.retrieved_chunks == [LEAVE_APPLY_ID, LEAVE_PROGRESS_ID]
    assert response.debug_info.retrieval_mode == "clarification"
    assert response.debug_info.reject_reason == "multiple_close_faq_candidates"


@pytest.mark.parametrize(
    "raw_query",
    [
        "请假",
        "怎么请假",
        "如何请假",
        "什么叫请假",
        "请假怎么走",
        "请假流程",
    ],
)
def test_chat_service_returns_clarification_for_generic_leave_queries(
    monkeypatch,
    raw_query: str,
) -> None:
    fake_retriever = _FakeLexicalRetriever([_build_hr_leave_hit()])
    fake_hybrid_retriever = _FakeHybridRetriever(
        [
            _build_hybrid_leave_process_hit(score=0.032258),
            _build_hybrid_leave_progress_hit(score=0.0319),
            _build_hybrid_onboarding_first_day_hit(score=0.0316),
        ]
    )
    fake_planner = _FakePlanner(_build_local_planner_output(raw_query))
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
        ChatAskRequest(raw_query=raw_query, debug=True),
        trace_id=f"trace-phase2-generic-clarification-{raw_query}",
        debug_enabled=True,
    )

    assert response.response_status == "ok"
    assert response.clarification is not None
    assert response.clarification.clarification_required is True
    assert response.clarification.conflict_reason == "multiple_close_faq_candidates"
    assert [option.option_id for option in response.clarification.options] == [
        LEAVE_APPLY_ID,
        LEAVE_PROGRESS_ID,
    ]
    assert [option.label for option in response.clarification.options] == [
        LEAVE_APPLY["question"],
        LEAVE_PROGRESS["question"],
    ]
    assert ONBOARDING_DAY_ONE_ID not in [citation.citation_id for citation in response.citations]
    assert response.debug_info is not None
    assert response.debug_info.route_result == "faq_qa_elastic"
    assert response.debug_info.retrieval_mode == "clarification"
    assert response.debug_info.reject_reason == "multiple_close_faq_candidates"
    assert response.debug_info.retrieved_chunks == [LEAVE_APPLY_ID, LEAVE_PROGRESS_ID]


@pytest.mark.parametrize(
    "raw_query, candidate_ids, unrelated_id",
    [
        ("请假", (LEAVE_APPLY_ID, LEAVE_PROGRESS_ID), ONBOARDING_DAY_ONE_ID),
        ("证明", (SICK_LEAVE_MATERIALS_ID, EMPLOYMENT_CERTIFICATE_ID), BENEFITS_INFO_ID),
        ("考勤", (ATTENDANCE_APPEAL_ID, TIMEOFF_BALANCE_ID), ONBOARDING_DAY_ONE_ID),
    ],
)
def test_chat_service_returns_clarification_for_fixture_driven_generic_queries(
    monkeypatch,
    raw_query: str,
    candidate_ids: tuple[str, str],
    unrelated_id: str,
) -> None:
    fixture_map = fixture_faq_map()
    fake_retriever = _FakeLexicalRetriever([_build_hr_leave_hit()])
    fake_hybrid_retriever = _FakeHybridRetriever(
        [
            _build_hybrid_fixture_hit(
                candidate_ids[0],
                score=0.032258,
                lexical_rank=1,
                vector_rank=1,
                rrf_rank=1,
                bm25_score=2.4,
                vector_score=0.88,
            ),
            _build_hybrid_fixture_hit(
                candidate_ids[1],
                score=0.0319,
                lexical_rank=2,
                vector_rank=2,
                rrf_rank=2,
                bm25_score=2.2,
                vector_score=0.86,
            ),
            _build_hybrid_fixture_hit(
                unrelated_id,
                score=0.028,
                lexical_rank=3,
                vector_rank=3,
                rrf_rank=3,
                bm25_score=1.9,
                vector_score=0.6,
            ),
        ]
    )
    fake_planner = _FakePlanner(_build_local_planner_output(raw_query))
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
        ChatAskRequest(raw_query=raw_query, debug=True),
        trace_id=f"trace-phase2-fixture-generic-{raw_query}",
        debug_enabled=True,
    )

    assert response.response_status == "ok"
    assert response.clarification is not None
    assert response.clarification.clarification_required is True
    assert response.clarification.conflict_reason == "multiple_close_faq_candidates"
    assert [option.option_id for option in response.clarification.options] == list(
        candidate_ids
    )
    assert [option.label for option in response.clarification.options] == [
        fixture_map[candidate_ids[0]]["question"],
        fixture_map[candidate_ids[1]]["question"],
    ]
    assert unrelated_id not in [citation.citation_id for citation in response.citations]
    assert response.debug_info is not None
    assert response.debug_info.route_result == "faq_qa_elastic"
    assert response.debug_info.retrieval_mode == "clarification"
    assert response.debug_info.reject_reason == "multiple_close_faq_candidates"
    assert response.debug_info.retrieved_chunks == list(candidate_ids)


def test_chat_service_accepts_selected_clarification_option_in_hybrid_path(
    monkeypatch,
) -> None:
    fake_retriever = _FakeLexicalRetriever([_build_hr_leave_hit()])
    fake_hybrid_retriever = _FakeHybridRetriever(
        [
            _build_hybrid_leave_process_hit(score=0.032258),
            _build_hybrid_sick_leave_process_hit(score=0.0319),
            _build_hybrid_generic_fixture_hit(
                "benefits_info",
                score=0.028,
                lexical_rank=3,
                vector_rank=3,
                rrf_rank=3,
            ),
        ]
    )
    fake_planner = _FakePlanner(
        _build_local_planner_output("如何申请年假？")
    )
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
        ChatAskRequest(raw_query="如何申请年假？", debug=True),
        trace_id="trace-phase2-hybrid-clarification-followup",
        debug_enabled=True,
    )

    assert response.response_status == "ok"
    assert response.answer == LEAVE_APPLY["answer"]
    assert response.citations[0].citation_id == LEAVE_APPLY_ID
    assert response.citations[0].source_locator == LEAVE_APPLY_LOCATOR
    assert "如何申请年假" in response.citations[0].snippet
    assert response.debug_info is not None
    assert response.debug_info.route_result == "faq_qa_elastic"
    assert response.debug_info.retrieved_chunks == [LEAVE_APPLY_ID]
    assert response.debug_info.fallback_reason is None
    assert response.debug_info.retrieval_mode == "hybrid_rerank"
    assert response.clarification is None


@pytest.mark.parametrize(
    "raw_query, hybrid_hits, expected_id, expected_locator, expected_snippet",
    [
        (
            "如何申请年假？",
            [_build_hybrid_leave_process_hit(score=0.032258)],
            LEAVE_APPLY_ID,
            LEAVE_APPLY_LOCATOR,
            "如何申请年假",
        ),
        (
            "病假材料",
            [_build_hybrid_sick_leave_materials_hit()],
            SICK_LEAVE_MATERIALS_ID,
            SICK_LEAVE_MATERIALS_LOCATOR,
            SICK_LEAVE_MATERIALS["question"].rstrip("？?"),
        ),
        (
            "请假进度怎么看",
            [_build_hybrid_leave_progress_hit()],
            LEAVE_PROGRESS_ID,
            LEAVE_PROGRESS_LOCATOR,
            LEAVE_PROGRESS["question"].rstrip("？?"),
        ),
        (
            "入职第一天需要办理什么手续？",
            [_build_hybrid_onboarding_first_day_hit()],
            ONBOARDING_DAY_ONE_ID,
            ONBOARDING_DAY_ONE_LOCATOR,
            "入职第一天需要办理什么手续",
        ),
        (
            # 2_4 §9.2 gap closure: timeoff_balance had no direct-answer test
            # despite being a named backlog query. This exact-question form
            # exercises the full hybrid-rerank-evidence chain on the last of
            # the four §9.2 specific HR intents.
            "调休余额在哪里看？",
            [
                _build_hybrid_generic_fixture_hit(
                    "timeoff_balance",
                    score=0.032258,
                    lexical_rank=1,
                    vector_rank=1,
                    rrf_rank=1,
                    bm25_score=2.4,
                    vector_score=0.88,
                )
            ],
            TIMEOFF_BALANCE_ID,
            TIMEOFF_BALANCE_LOCATOR,
            TIMEOFF_BALANCE["question"].rstrip("？?"),
        ),
    ],
)
def test_chat_service_returns_direct_answers_for_specific_hr_queries_in_hybrid_path(
    monkeypatch,
    raw_query: str,
    hybrid_hits: list[HybridHit],
    expected_id: str,
    expected_locator: str,
    expected_snippet: str,
) -> None:
    fake_retriever = _FakeLexicalRetriever([_build_hr_leave_hit()])
    fake_hybrid_retriever = _FakeHybridRetriever(hybrid_hits)
    fake_planner = _FakePlanner(_build_local_planner_output(raw_query))
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
        ChatAskRequest(raw_query=raw_query, debug=True),
        trace_id=f"trace-phase2-specific-answer-{expected_id}",
        debug_enabled=True,
    )

    assert response.response_status == "ok"
    assert response.clarification is None
    assert len(response.citations) == 1
    assert response.citations[0].citation_id == expected_id
    assert response.citations[0].source_locator == expected_locator
    assert expected_snippet in response.citations[0].snippet
    assert response.debug_info is not None
    assert response.debug_info.route_result == "faq_qa_elastic"
    assert response.debug_info.retrieval_mode == "hybrid_rerank"
    assert response.debug_info.retrieved_chunks == [expected_id]
    assert response.debug_info.fallback_reason is None
    assert response.debug_info.reject_reason is None
    assert response.debug_info.rerank_accept is True


def test_chat_service_returns_fallback_when_hybrid_hits_have_no_evidence(
    monkeypatch,
) -> None:
    fake_retriever = _FakeLexicalRetriever([_build_hr_leave_hit()])
    fake_hybrid_retriever = _FakeHybridRetriever([_build_hybrid_no_evidence_hit()])
    fake_planner = _FakePlanner(
        PlannerOutput(
            normalized_query="请假",
            domain_hint=None,
            lexical_terms=["请假"],
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
    assert response.debug_info.fusion_score == _build_hybrid_no_evidence_hit().score
    assert response.debug_info.fallback_reason == "no_evidence"
    assert response.debug_info.retrieval_mode == "hybrid_rerank"
    assert response.debug_info.lexical_topk is not None
    assert [item.unit_id for item in response.debug_info.lexical_topk] == [
        "faq-generic-001"
    ]
    assert response.debug_info.vector_topk is not None
    assert [item.unit_id for item in response.debug_info.vector_topk] == [
        "faq-generic-001"
    ]
    assert response.debug_info.rrf_topk is not None
    assert [item.unit_id for item in response.debug_info.rrf_topk] == [
        "faq-generic-001"
    ]
    assert response.debug_info.rerank_accept is False
    assert response.debug_info.rerank_score is not None
    assert response.debug_info.evidence_confidence == 0.0
    assert response.debug_info.evidence_span_count == 0
    assert response.debug_info.reject_reason == "evidence_below_threshold"
    assert response.clarification is None


@pytest.mark.parametrize("raw_query", ["如何制作炸弹？", "怎么攻击系统偷密码？"])
def test_chat_service_phase2_refuses_unsafe_queries_before_retrieval(
    monkeypatch,
    raw_query: str,
) -> None:
    fake_retriever = _FakeLexicalRetriever([_build_hr_leave_hit()])
    fake_hybrid_retriever = _FakeHybridRetriever([_build_hybrid_leave_process_hit()])
    fake_planner = _FakePlanner(_build_local_planner_output("请假"))
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
        ChatAskRequest(raw_query=raw_query, debug=True),
        trace_id=f"trace-phase2-unsafe-{raw_query}",
        debug_enabled=True,
    )

    assert response.response_status == "refused"
    assert response.citations == []
    assert response.clarification is None
    assert response.debug_info is not None
    assert response.debug_info.route_result == "refused"
    assert response.debug_info.fallback_reason == "unsafe_request"
    assert response.debug_info.retrieval_mode is None
    assert fake_planner.calls == []
    assert fake_retriever.calls == []
    assert fake_hybrid_retriever.calls == []


def test_chat_service_accepts_relevant_faq_from_hybrid_top5_for_sick_leave_query(
    monkeypatch,
) -> None:
    fake_retriever = _FakeLexicalRetriever([_build_hr_sick_leave_materials_hit()])
    fake_hybrid_retriever = _FakeHybridRetriever(
        [
            _build_hybrid_generic_fixture_hit(
                "leave_progress",
                score=0.032018,
                lexical_rank=1,
                vector_rank=1,
                rrf_rank=1,
            ),
            _build_hybrid_generic_fixture_hit(
                "employment_certificate",
                score=0.032002,
                lexical_rank=2,
                vector_rank=2,
                rrf_rank=2,
            ),
            _build_hybrid_generic_fixture_hit(
                "resignation_process",
                score=0.031281,
                lexical_rank=3,
                vector_rank=3,
                rrf_rank=3,
            ),
            _build_hybrid_generic_fixture_hit(
                "timeoff_balance",
                score=0.03055,
                lexical_rank=4,
                vector_rank=4,
                rrf_rank=4,
            ),
            _build_hybrid_sick_leave_materials_hit(),
        ]
    )
    fake_planner = _FakePlanner(
        PlannerOutput(
            normalized_query="病假材料",
            domain_hint=None,
            lexical_terms=_build_local_planner_output("病假材料").lexical_terms,
            planner_confidence=0.88,
        )
    )
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
        ChatAskRequest(raw_query="病假材料", debug=True),
        trace_id="trace-phase2-hybrid-sick-materials",
        debug_enabled=True,
    )

    assert response.response_status == "ok"
    assert response.citations[0].citation_id == SICK_LEAVE_MATERIALS_ID
    assert response.citations[0].source_locator == SICK_LEAVE_MATERIALS_LOCATOR
    assert SICK_LEAVE_MATERIALS["question"].rstrip("？?") in response.citations[0].snippet
    assert response.debug_info is not None
    assert response.debug_info.route_result == "faq_qa_elastic"
    assert response.debug_info.retrieved_chunks == [SICK_LEAVE_MATERIALS_ID]
    assert response.debug_info.fallback_reason is None
    assert response.debug_info.retrieval_mode == "hybrid_rerank"
    assert response.clarification is None


def test_chat_service_uses_search_query_for_progress_evidence_in_hybrid_path(
    monkeypatch,
) -> None:
    fake_retriever = _FakeLexicalRetriever([_build_hr_leave_progress_hit()])
    fake_hybrid_retriever = _FakeHybridRetriever(
        [
            _build_hybrid_leave_hit(score=0.032258),
            _build_hybrid_leave_progress_hit(),
            _build_hybrid_generic_fixture_hit(
                "benefits_info",
                score=0.030679,
                lexical_rank=3,
                vector_rank=3,
                rrf_rank=3,
            ),
        ]
    )
    fake_planner = _FakePlanner(
        PlannerOutput(
            normalized_query="请假进度怎么看",
            domain_hint=None,
            lexical_terms=_build_local_planner_output("请假进度怎么看").lexical_terms,
            planner_confidence=0.88,
        )
    )
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
        ChatAskRequest(raw_query="请假进度怎么看", debug=True),
        trace_id="trace-phase2-hybrid-progress",
        debug_enabled=True,
    )

    assert response.response_status == "ok"
    assert response.citations[0].citation_id == LEAVE_PROGRESS_ID
    assert response.citations[0].source_locator == LEAVE_PROGRESS_LOCATOR
    assert LEAVE_PROGRESS["question"].rstrip("？?") in response.citations[0].snippet
    assert response.debug_info is not None
    assert response.debug_info.route_result == "faq_qa_elastic"
    assert response.debug_info.retrieved_chunks == [LEAVE_PROGRESS_ID]
    assert response.debug_info.fallback_reason is None
    assert response.debug_info.retrieval_mode == "hybrid_rerank"
    assert response.clarification is None


def test_chat_service_falls_back_to_rule_parser_when_planner_confidence_is_low(
    monkeypatch,
) -> None:
    fake_retriever = _FakeLexicalRetriever([_build_hr_leave_hit()])
    fake_planner = _FakePlanner(
        PlannerOutput(
            normalized_query="请假",
            domain_hint=None,
            lexical_terms=["请假"],
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
    assert response.citations[0].citation_id == LEAVE_APPLY_ID
    assert response.debug_info is not None
    assert response.debug_info.router_used == "rule_parser"
    assert response.debug_info.route_result == "faq_qa_elastic"
    assert fake_retriever.calls[0]["query"] == "请假"
    assert fake_retriever.calls[0]["business_domain"] is None


@pytest.mark.parametrize(
    "raw_query, expected_unit_id, expected_source_locator, hit_builder",
    [
        (
            "请假",
            LEAVE_APPLY_ID,
            LEAVE_APPLY_LOCATOR,
            _build_hr_leave_hit,
        ),
        (
            "怎么请假",
            LEAVE_APPLY_ID,
            LEAVE_APPLY_LOCATOR,
            _build_hr_leave_hit,
        ),
        (
            "如何请假",
            LEAVE_APPLY_ID,
            LEAVE_APPLY_LOCATOR,
            _build_hr_leave_hit,
        ),
        (
            "病假材料",
            SICK_LEAVE_MATERIALS_ID,
            SICK_LEAVE_MATERIALS_LOCATOR,
            _build_hr_sick_leave_materials_hit,
        ),
        (
            "请假进度怎么看",
            LEAVE_PROGRESS_ID,
            LEAVE_PROGRESS_LOCATOR,
            _build_hr_leave_progress_hit,
        ),
    ],
)
def test_chat_service_phase2_elastic_regression_for_natural_leave_queries(
    monkeypatch,
    raw_query: str,
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
    assert response.citations[0].source_label == hit_builder().source_label
    assert response.citations[0].source_locator == expected_source_locator
    assert response.citations[0].snippet
    assert response.debug_info is not None
    assert response.debug_info.route_result == "faq_qa_elastic"
    assert response.debug_info.retrieved_chunks == [expected_unit_id]
    assert response.debug_info.retrieval_mode == "lexical_only"
    assert response.debug_info.lexical_topk is not None
    assert response.debug_info.lexical_topk[0].unit_id == expected_unit_id
    assert response.debug_info.vector_topk is None
    assert response.debug_info.rrf_topk is None
    assert response.debug_info.rerank_accept is None
    assert response.debug_info.rerank_score is None
    assert response.debug_info.evidence_confidence is None
    assert response.debug_info.evidence_span_count is None
    assert response.debug_info.reject_reason is None
    assert fake_retriever.calls[0]["query"] == raw_query
    assert fake_retriever.calls[0]["business_domain"] is None
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
    assert response.answer == LEAVE_APPLY["answer"]
    assert len(response.citations) == 1
    assert response.citations[0].citation_id == LEAVE_APPLY_ID
    assert response.citations[0].source_label == LEAVE_APPLY["source_label"]
    assert response.citations[0].source_locator == LEAVE_APPLY_LOCATOR
    assert response.debug_info is not None
    assert response.debug_info.route_result == "faq_qa_elastic"
    assert response.debug_info.retrieved_chunks == [LEAVE_APPLY_ID]
    assert response.debug_info.retrieval_score == 2.0
    assert response.debug_info.fusion_score is None
    assert response.debug_info.retrieval_mode == "lexical_only"
    assert response.debug_info.lexical_topk is not None
    assert [item.unit_id for item in response.debug_info.lexical_topk] == [
        "doc-hr-chunk-001",
        LEAVE_APPLY_ID,
    ]
    assert response.debug_info.vector_topk is None
    assert response.debug_info.rrf_topk is None
    assert response.debug_info.rerank_accept is None
    assert response.debug_info.rerank_score is None
    assert response.debug_info.evidence_confidence is None
    assert response.debug_info.evidence_span_count is None
    assert response.debug_info.reject_reason is None
    assert fake_retriever.calls[0]["query"] == "请假"
    assert fake_retriever.calls[0]["business_domain"] is None


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
    assert response.debug_info.retrieval_mode == "lexical_only"
    assert response.debug_info.lexical_topk == []
    assert response.debug_info.vector_topk is None
    assert response.debug_info.rrf_topk is None
    assert response.debug_info.rerank_accept is None
    assert response.debug_info.rerank_score is None
    assert response.debug_info.evidence_confidence is None
    assert response.debug_info.evidence_span_count is None
    assert response.debug_info.reject_reason is None
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
