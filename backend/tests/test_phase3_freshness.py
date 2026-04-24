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


def test_freshness_stale_appends_warning_to_answer() -> None:
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
