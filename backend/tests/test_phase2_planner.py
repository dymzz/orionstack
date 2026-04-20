from app.config.settings import Settings
from app.query.query_planner import PlannerOutput, QueryPlanner
from app.routing.contracts import IntentDecision
from app.schemas.request import ChatAskRequest
from app.services import chat_service as chat_service_module
from app.services.chat_service import ChatService
from conftest import fixture_case


LEAVE_APPLY = fixture_case("leave_apply")


class _FakeLexicalRetriever:
    def __init__(self, hits):
        self._hits = list(hits)
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


def _build_faq_hit():
    from app.retrieval.lexical_retriever import LexicalHit

    return LexicalHit(
        unit_id=LEAVE_APPLY["id"],
        source_kind="faq",
        question=LEAVE_APPLY["question"],
        answer=LEAVE_APPLY["answer"],
        body_text=LEAVE_APPLY["answer"],
        source_label=LEAVE_APPLY["source_label"],
        source_locator=LEAVE_APPLY["source_locator"],
        score=3.2,
        business_domain=LEAVE_APPLY["business_domain"],
        document_type=LEAVE_APPLY["document_type"],
        source_type=LEAVE_APPLY["source_type"],
        access_scope=LEAVE_APPLY["access_scope"],
        lifecycle_status=LEAVE_APPLY["lifecycle_status"],
    )


def test_query_planner_outputs_minimal_fields_for_non_empty_query() -> None:
    planner = QueryPlanner(provider="local", model="stub")

    output = planner.plan("请假")

    assert output.normalized_query == "请假"
    assert output.domain_hint is None
    assert output.lexical_terms[0] == "请假"
    assert "请假" in output.lexical_terms
    assert output.planner_confidence >= 0.15


def test_chat_service_uses_planner_outputs_for_elasticsearch_lexical_path(
    monkeypatch,
) -> None:
    fake_retriever = _FakeLexicalRetriever([_build_faq_hit()])
    fake_planner = _FakePlanner(
        PlannerOutput(
            normalized_query="请假",
            domain_hint=None,
            lexical_terms=["请假"],
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
        ),
    )
    monkeypatch.setattr(
        ChatService,
        "_create_query_planner",
        lambda self: fake_planner,
    )
    monkeypatch.setattr(
        ChatService,
        "_create_lexical_retriever",
        lambda self: fake_retriever,
    )
    monkeypatch.setattr(ChatService, "_create_hybrid_retriever", lambda self: None)

    service = ChatService()
    response = service.ask(
        ChatAskRequest(raw_query="请假", debug=True),
        trace_id="trace-phase2-planner-elastic",
        debug_enabled=True,
    )

    assert fake_planner.calls == ["请假"]
    assert response.response_status == "ok"
    assert response.debug_info is not None
    assert response.debug_info.route_result == "faq_qa_elastic"
    assert response.debug_info.router_used == "query_planner_local"
    assert response.debug_info.retrieved_chunks == [LEAVE_APPLY["id"]]
    assert response.debug_info.retrieval_mode == "lexical_only"
    assert response.debug_info.lexical_topk is not None
    assert response.debug_info.lexical_topk[0].unit_id == LEAVE_APPLY["id"]
    assert response.debug_info.lexical_topk[0].source_kind == "faq"
    assert response.debug_info.vector_topk is None
    assert response.debug_info.rrf_topk is None
    assert response.debug_info.rerank_accept is None
    assert response.debug_info.rerank_score is None
    assert response.debug_info.evidence_confidence is None
    assert response.debug_info.evidence_span_count is None
    assert response.debug_info.reject_reason is None
    assert response.citations[0].source_locator == LEAVE_APPLY["source_locator"]
    assert fake_retriever.calls[0]["query"] == "请假"
    assert fake_retriever.calls[0]["lexical_terms"] == ["请假"]
    assert fake_retriever.calls[0]["business_domain"] is None


def test_chat_service_falls_back_to_rule_parser_when_planner_confidence_is_low(
    monkeypatch,
) -> None:
    fake_retriever = _FakeLexicalRetriever([_build_faq_hit()])
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
        "_create_query_planner",
        lambda self: fake_planner,
    )
    monkeypatch.setattr(
        ChatService,
        "_create_lexical_retriever",
        lambda self: fake_retriever,
    )
    monkeypatch.setattr(ChatService, "_create_hybrid_retriever", lambda self: None)

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
    assert response.debug_info is not None
    assert response.debug_info.router_used == "rule_parser"
    assert response.debug_info.route_result == "faq_qa_elastic"
    assert response.debug_info.retrieval_mode == "lexical_only"
    assert response.debug_info.lexical_topk is not None
    assert response.debug_info.lexical_topk[0].unit_id == LEAVE_APPLY["id"]
    assert response.debug_info.vector_topk is None
    assert response.debug_info.rrf_topk is None
    assert response.debug_info.rerank_accept is None
    assert response.debug_info.rerank_score is None
    assert response.debug_info.evidence_confidence is None
    assert response.debug_info.evidence_span_count is None
    assert response.debug_info.reject_reason is None
    assert fake_retriever.calls[0]["query"] == "请假"
    assert fake_retriever.calls[0]["business_domain"] is None
