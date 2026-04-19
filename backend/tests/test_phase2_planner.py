from app.config.settings import Settings
from app.query.query_planner import PlannerOutput, QueryPlanner
from app.routing.contracts import IntentDecision
from app.schemas.request import ChatAskRequest
from app.services import chat_service as chat_service_module
from app.services.chat_service import ChatService


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
        unit_id="hr-faq-001",
        source_kind="faq",
        question="如何申请年假？",
        answer="进入公司请假入口后选择年假，填写请假时间与原因并提交审批。",
        body_text="进入公司请假入口后选择年假，填写请假时间与原因并提交审批。",
        source_label="HR FAQ",
        source_locator="hr_faq_seed_v1#hr-faq-001",
        score=3.2,
        business_domain="hr",
        document_type="faq",
        source_type="manual_faq",
        access_scope="internal",
        lifecycle_status="active",
    )


def test_query_planner_outputs_minimal_hr_fields_for_leave_query() -> None:
    planner = QueryPlanner(provider="local", model="stub")

    output = planner.plan("请假")

    assert output.normalized_query == "请假"
    assert output.domain_hint == "hr"
    assert output.lexical_terms[0] == "请假"
    assert "请假" in output.lexical_terms
    assert "审批" in output.lexical_terms
    assert output.planner_confidence >= 0.15


def test_chat_service_uses_planner_outputs_for_elasticsearch_lexical_path(
    monkeypatch,
) -> None:
    fake_retriever = _FakeLexicalRetriever([_build_faq_hit()])
    fake_planner = _FakePlanner(
        PlannerOutput(
            normalized_query="请假 审批",
            domain_hint="hr",
            lexical_terms=["请假", "审批"],
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
    assert response.debug_info.retrieved_chunks == ["hr-faq-001"]
    assert response.citations[0].source_locator == "hr_faq_seed_v1#hr-faq-001"
    assert fake_retriever.calls[0]["query"] == "请假 审批"
    assert fake_retriever.calls[0]["lexical_terms"] == ["请假", "审批"]
    assert fake_retriever.calls[0]["business_domain"] == "hr"


def test_chat_service_falls_back_to_rule_parser_when_planner_confidence_is_low(
    monkeypatch,
) -> None:
    fake_retriever = _FakeLexicalRetriever([_build_faq_hit()])
    fake_planner = _FakePlanner(
        PlannerOutput(
            normalized_query="请假 审批",
            domain_hint="hr",
            lexical_terms=["请假", "审批"],
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
    assert fake_retriever.calls[0]["query"] == "请假 申请 审批 流程"
    assert fake_retriever.calls[0]["business_domain"] == "hr"
