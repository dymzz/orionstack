import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

from app.api.routes import chat as chat_route
from app.config.settings import Settings
from app.schemas.request import ChatAskRequest
from app.schemas.response import ChatAskResponse, DebugInfo
from app.sync.freshness import check_freshness
from app.sync.freshness_checker import FreshnessResult
from conftest import fixture_case


LEAVE_APPLY = fixture_case("leave_apply")


class _FakeLexicalRetriever:
    def __init__(self, hits) -> None:
        self._hits = hits

    def search(self, query: str, **kwargs):
        return list(self._hits)


def _configure_trace_storage(tmp_path: Path) -> None:
    chat_route.feedback_repository._path = tmp_path / "feedback_records.jsonl"
    chat_route.chat_record_repository._path = tmp_path / "chat_records.jsonl"
    chat_route.retrieval_trace_repository._path = tmp_path / "retrieval_traces.jsonl"
    chat_route.hard_cases_repository._path = tmp_path / "hard_cases.jsonl"


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_check_freshness_returns_fresh_when_no_limits() -> None:
    result = check_freshness(None, None)
    assert result.is_fresh
    assert result.status == "fresh"


def test_check_freshness_returns_fresh_before_deadline() -> None:
    future = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    result = check_freshness(future, None)
    assert result.is_fresh


def test_check_freshness_returns_warning_in_warning_zone() -> None:
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    result = check_freshness(past, future)
    assert result.is_warning
    assert result.status == "warning"


def test_check_freshness_returns_stale_after_all_deadlines() -> None:
    past1 = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    past2 = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
    result = check_freshness(past1, past2)
    assert result.is_stale
    assert result.status == "stale"


def test_freshness_result_properties() -> None:
    fresh = FreshnessResult(status="fresh", fresh_until=None, stale_after=None)
    assert fresh.is_fresh
    assert not fresh.is_warning
    assert not fresh.is_stale

    warning = FreshnessResult(status="warning", fresh_until="x", stale_after="y")
    assert not warning.is_fresh
    assert warning.is_warning
    assert not warning.is_stale

    stale = FreshnessResult(status="stale", fresh_until="x", stale_after="y")
    assert not stale.is_fresh
    assert not stale.is_warning
    assert stale.is_stale


def test_freshness_stale_detected() -> None:
    from app.retrieval.hybrid_retriever import HybridHit
    from app.services.chat_service import ChatService

    past = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    stale_hit = HybridHit(
        unit_id="unit-stale-001",
        source_kind="faq",
        question="如何上传文档？",
        answer="请上传到 OA 系统即可。",
        body_text="请上传到 OA 系统即可。",
        source_label="FAQ",
        source_locator="faq#001",
        score=0.05,
        business_domain="hr",
        document_type="faq",
        source_type="manual_faq",
        access_scope="internal",
        lifecycle_status="active",
        bm25_score=2.0,
        vector_score=0.9,
        lexical_rank=1,
        vector_rank=1,
        rrf_rank=1,
        fresh_until=past,
        stale_after=past,
    )

    result = ChatService._check_hit_freshness(stale_hit)
    assert result is not None
    assert result.is_stale


def test_stale_elastic_hit_returns_safe_fallback_with_action_link(
    monkeypatch, tmp_path
) -> None:
    from app.retrieval.lexical_retriever import LexicalHit
    from app.services import chat_service as chat_service_module
    from app.services.chat_service import ChatService
    from app.storage.models.action_link import ActionLink
    from app.storage.repositories.action_link_repo import ActionLinkRepo

    past = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    stale_answer = "请上传到 OA 系统即可。"
    stale_hit = LexicalHit(
        unit_id="unit-stale-001",
        source_kind="faq",
        question="如何上传文档？",
        answer=stale_answer,
        body_text=stale_answer,
        source_label="FAQ",
        source_locator="faq#001",
        score=2.5,
        business_domain="hr",
        document_type="faq",
        source_type="manual_faq",
        access_scope="internal",
        lifecycle_status="active",
        source_record_id="sr-stale-001",
        import_batch_id="ib-stale-001",
        unit_version=2,
        fresh_until=past,
        stale_after=past,
    )
    action_repo = ActionLinkRepo(storage_dir=tmp_path / "action_links")
    action_repo.create(
        ActionLink(
            action_link_id="al-stale-001",
            tenant_id="default",
            source_record_id="sr-stale-001",
            label="去原系统核实",
            system_type="manual_export",
            url="https://example.com/source",
            resource_type="policy_doc",
            access_scope="internal",
            status="active",
            published_at="2026-01-01T00:00:00Z",
            business_domains=("hr",),
        )
    )
    monkeypatch.setattr(
        "app.storage.repositories.action_link_repo._STORAGE_DIR",
        tmp_path / "action_links",
    )
    monkeypatch.setattr(
        chat_service_module,
        "settings",
        Settings(search_backend="elasticsearch", enable_query_planner=False),
    )
    monkeypatch.setattr(
        ChatService,
        "_create_lexical_retriever",
        lambda self: _FakeLexicalRetriever([stale_hit]),
    )
    monkeypatch.setattr(ChatService, "_create_hybrid_retriever", lambda self: None)

    service = ChatService()
    response = service.ask(
        ChatAskRequest(raw_query="如何上传文档？", debug=True),
        trace_id="trace-stale-safe",
        debug_enabled=True,
    )

    assert response.response_status == "fallback"
    assert stale_answer not in response.answer
    assert "过期" in response.answer
    assert response.citations == []
    assert [link.label for link in response.action_links] == ["去原系统核实"]
    assert response.debug_info is not None
    assert response.debug_info.fallback_reason == "stale_knowledge"
    assert response.debug_info.freshness_status == "stale"
    assert response.debug_info.source_record_id == "sr-stale-001"
    assert response.debug_info.import_batch_id == "ib-stale-001"
    assert response.debug_info.unit_version == 2


def test_stale_fallback_trace_records_freshness_hard_case(
    monkeypatch, tmp_path
) -> None:
    _configure_trace_storage(tmp_path)
    monkeypatch.setattr(chat_route, "settings", Settings(app_mode="demo"))

    def return_stale(payload, *, trace_id: str, debug_enabled: bool):
        return ChatAskResponse(
            response_status="fallback",
            trace_id=trace_id,
            answer="命中的知识内容已过期，我先不直接给出原答案。",
            citations=[],
            debug_info=DebugInfo(
                normalized_query=payload.raw_query.strip(),
                route_result="faq_qa_elastic",
                router_used="query_planner_local",
                retrieved_chunks=["unit-stale-001"],
                route_confidence=None,
                retrieval_score=2.5,
                fallback_reason="stale_knowledge",
                freshness_status="stale",
                source_record_id="sr-stale-001",
                import_batch_id="ib-stale-001",
                unit_version=2,
            ),
        )

    monkeypatch.setattr(chat_route.service, "ask", return_stale)

    response = chat_route.ask_chat(ChatAskRequest(raw_query="如何上传文档？", debug=True))

    assert response.response_status == "fallback"
    trace = _load_jsonl(tmp_path / "retrieval_traces.jsonl")
    assert trace[0]["fallback_reason"] == "stale_knowledge"
    assert trace[0]["freshness_status"] == "stale"
    hard_cases = _load_jsonl(tmp_path / "hard_cases.jsonl")
    assert len(hard_cases) == 1
    assert hard_cases[0]["issue_category"] == "freshness_stale"
    assert hard_cases[0]["source_record_id"] == "sr-stale-001"


def test_freshness_warning_detected() -> None:
    from app.retrieval.hybrid_retriever import HybridHit
    from app.services.chat_service import ChatService

    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    warning_hit = HybridHit(
        unit_id="unit-warn-001",
        source_kind="faq",
        question="年假怎么申请？",
        answer="年假需要提前三天申请。",
        body_text="年假需要提前三天申请。",
        source_label="FAQ",
        source_locator="faq#002",
        score=0.05,
        business_domain="hr",
        document_type="faq",
        source_type="manual_faq",
        access_scope="internal",
        lifecycle_status="active",
        bm25_score=2.0,
        vector_score=0.9,
        lexical_rank=1,
        vector_rank=1,
        rrf_rank=1,
        fresh_until=past,
        stale_after=future,
    )

    result = ChatService._check_hit_freshness(warning_hit)
    assert result is not None
    assert result.is_warning


def test_warning_elastic_hit_still_answers_with_freshness_notice(
    monkeypatch,
) -> None:
    from app.retrieval.lexical_retriever import LexicalHit
    from app.services import chat_service as chat_service_module
    from app.services.chat_service import ChatService

    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    warning_answer = "年假需要提前三天申请。"
    warning_hit = LexicalHit(
        unit_id="unit-warning-001",
        source_kind="faq",
        question="年假怎么申请？",
        answer=warning_answer,
        body_text=warning_answer,
        source_label="FAQ",
        source_locator="faq#002",
        score=2.5,
        business_domain="hr",
        document_type="faq",
        source_type="manual_faq",
        access_scope="internal",
        lifecycle_status="active",
        fresh_until=past,
        stale_after=future,
    )
    monkeypatch.setattr(
        chat_service_module,
        "settings",
        Settings(search_backend="elasticsearch", enable_query_planner=False),
    )
    monkeypatch.setattr(
        ChatService,
        "_create_lexical_retriever",
        lambda self: _FakeLexicalRetriever([warning_hit]),
    )
    monkeypatch.setattr(ChatService, "_create_hybrid_retriever", lambda self: None)

    service = ChatService()
    response = service.ask(
        ChatAskRequest(raw_query="年假怎么申请？", debug=True),
        trace_id="trace-warning-answer",
        debug_enabled=True,
    )

    assert response.response_status == "ok"
    assert warning_answer in response.answer
    assert "可能即将过期" in response.answer
    assert response.citations
    assert response.debug_info is not None
    assert response.debug_info.freshness_status == "warning"


def test_freshness_fresh_does_not_modify_answer(monkeypatch, tmp_path) -> None:
    _configure_trace_storage(tmp_path)
    monkeypatch.setattr(chat_route, "settings", Settings(app_mode="demo"))

    original_answer = "请上传到 OA 系统即可。"

    def return_fresh_hit(payload, *, trace_id: str, debug_enabled: bool):
        return ChatAskResponse(
            response_status="ok",
            trace_id=trace_id,
            answer=original_answer,
            citations=[],
            debug_info=DebugInfo(
                normalized_query=payload.raw_query.strip(),
                route_result="faq_qa_elastic",
                router_used="query_planner_local",
                retrieved_chunks=["unit-fresh-001"],
                route_confidence=None,
                retrieval_score=0.92,
                fusion_score=0.88,
                fallback_reason=None,
                retrieval_mode="hybrid_rerank",
                rerank_accept=True,
                rerank_score=0.85,
                evidence_confidence=0.9,
                evidence_span_count=2,
                freshness_status="fresh",
            ),
        )

    monkeypatch.setattr(chat_route.service, "ask", return_fresh_hit)

    response = chat_route.ask_chat(ChatAskRequest(raw_query="文档管理", debug=True))
    assert response.answer == original_answer


def test_freshness_no_status_does_not_modify_answer(monkeypatch, tmp_path) -> None:
    _configure_trace_storage(tmp_path)
    monkeypatch.setattr(chat_route, "settings", Settings(app_mode="demo"))

    original_answer = "请上传到 OA 系统即可。"

    def return_no_freshness(payload, *, trace_id: str, debug_enabled: bool):
        return ChatAskResponse(
            response_status="ok",
            trace_id=trace_id,
            answer=original_answer,
            citations=[],
            debug_info=DebugInfo(
                normalized_query=payload.raw_query.strip(),
                route_result="faq_qa_elastic",
                router_used="query_planner_local",
                retrieved_chunks=["unit-no-001"],
                route_confidence=None,
                retrieval_score=0.92,
                fusion_score=0.88,
                fallback_reason=None,
                retrieval_mode="hybrid_rerank",
                rerank_accept=True,
                rerank_score=0.85,
                evidence_confidence=0.9,
                evidence_span_count=2,
                freshness_status=None,
            ),
        )

    monkeypatch.setattr(chat_route.service, "ask", return_no_freshness)

    response = chat_route.ask_chat(ChatAskRequest(raw_query="文档管理", debug=True))
    assert response.answer == original_answer


def test_trace_captures_freshness_status(tmp_path) -> None:
    _configure_trace_storage(tmp_path)

    response = chat_route.ask_chat(
        ChatAskRequest(raw_query="如何上传文档？", debug=True)
    )

    trace = _load_jsonl(tmp_path / "retrieval_traces.jsonl")
    assert len(trace) == 1
    assert "freshness_status" in trace[0]
