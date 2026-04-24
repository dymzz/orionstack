import json
from pathlib import Path

import pytest

from app.api.routes import chat as chat_route
from app.config.settings import Settings
from app.schemas.request import ChatAskRequest, ChatFeedbackRequest
from app.schemas.response import (
    ChatAskResponse,
    DebugInfo,
    RetrievalCandidateSummary,
)
from conftest import fixture_case


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


LEAVE_APPLY = fixture_case("leave_apply")
SICK_LEAVE_MATERIALS = fixture_case("sick_leave_materials")


def test_trace_captures_phase3_provenance_fields(tmp_path) -> None:
    _configure_trace_storage(tmp_path)

    response = chat_route.ask_chat(
        ChatAskRequest(raw_query="如何上传文档？", debug=True)
    )

    trace = _load_jsonl(tmp_path / "retrieval_traces.jsonl")
    assert len(trace) == 1
    record = trace[0]
    assert "source_record_id" in record
    assert "import_batch_id" in record
    assert "unit_version" in record
    assert "dynamic_query_key" in record
    assert record["source_record_id"] is None
    assert record["import_batch_id"] is None
    assert record["unit_version"] is None
    assert record["dynamic_query_key"] is None


def test_trace_captures_provenance_when_source_record_attached(
    monkeypatch, tmp_path
) -> None:
    _configure_trace_storage(tmp_path)
    monkeypatch.setattr(chat_route, "settings", Settings(app_mode="demo"))

    def return_with_provenance(payload, *, trace_id: str, debug_enabled: bool):
        return ChatAskResponse(
            response_status="ok",
            trace_id=trace_id,
            answer="请上传到 OA 系统即可。",
            citations=[],
            debug_info=DebugInfo(
                normalized_query=payload.raw_query.strip(),
                route_result="faq_qa_elastic",
                router_used="query_planner_local",
                retrieved_chunks=["unit-001"],
                route_confidence=None,
                retrieval_score=0.92,
                fusion_score=0.88,
                fallback_reason=None,
                retrieval_mode="hybrid_rerank",
                lexical_topk=[
                    RetrievalCandidateSummary(
                        unit_id="unit-001", score=2.4, source_kind="faq"
                    )
                ],
                vector_topk=[
                    RetrievalCandidateSummary(
                        unit_id="unit-001", score=0.92, source_kind="faq"
                    )
                ],
                rrf_topk=[
                    RetrievalCandidateSummary(
                        unit_id="unit-001", score=0.016, source_kind="faq"
                    )
                ],
                rerank_accept=True,
                rerank_score=0.85,
                evidence_confidence=0.9,
                evidence_span_count=2,
                source_record_id="sr-hr-policy-001",
                import_batch_id="batch-2026-04-20",
                unit_version=3,
            ),
        )

    monkeypatch.setattr(chat_route.service, "ask", return_with_provenance)

    response = chat_route.ask_chat(ChatAskRequest(raw_query="文档管理", debug=True))

    assert response.response_status == "ok"
    trace = _load_jsonl(tmp_path / "retrieval_traces.jsonl")
    assert len(trace) == 1
    record = trace[0]
    assert record["source_record_id"] == "sr-hr-policy-001"
    assert record["import_batch_id"] == "batch-2026-04-20"
    assert record["unit_version"] == 3


def test_trace_captures_dynamic_query_key(monkeypatch, tmp_path) -> None:
    _configure_trace_storage(tmp_path)
    monkeypatch.setattr(chat_route, "settings", Settings(app_mode="demo"))

    def return_dynamic_query(payload, *, trace_id: str, debug_enabled: bool):
        return ChatAskResponse(
            response_status="ok",
            trace_id=trace_id,
            answer="已为您查询到 3 条请假记录。",
            citations=[],
            dynamic_query_result=None,
            debug_info=DebugInfo(
                normalized_query=payload.raw_query.strip(),
                route_result="dynamic_query",
                router_used="dynamic_query",
                retrieved_chunks=[],
                route_confidence=1.0,
                retrieval_mode=None,
                dynamic_query_key="my_leave_balance",
            ),
        )

    monkeypatch.setattr(chat_route.service, "ask", return_dynamic_query)

    response = chat_route.ask_chat(ChatAskRequest(raw_query="我的请假记录", debug=True))

    trace = _load_jsonl(tmp_path / "retrieval_traces.jsonl")
    assert len(trace) == 1
    assert trace[0]["dynamic_query_key"] == "my_leave_balance"
    assert trace[0]["source_record_id"] is None


def test_hard_case_carries_provenance_from_no_evidence(monkeypatch, tmp_path) -> None:
    _configure_trace_storage(tmp_path)
    monkeypatch.setattr(chat_route, "settings", Settings(app_mode="demo"))

    def return_no_evidence(payload, *, trace_id: str, debug_enabled: bool):
        return ChatAskResponse(
            response_status="fallback",
            trace_id=trace_id,
            answer="当前知识库中未命中足够依据。",
            citations=[],
            debug_info=DebugInfo(
                normalized_query=payload.raw_query.strip(),
                route_result="faq_qa_elastic",
                router_used="query_planner_local",
                retrieved_chunks=[],
                route_confidence=None,
                retrieval_score=None,
                fusion_score=0.028,
                fallback_reason="no_evidence",
                retrieval_mode="hybrid_rerank",
                rerank_accept=False,
                rerank_score=0.11,
                evidence_confidence=0.05,
                evidence_span_count=0,
                reject_reason="evidence_below_threshold",
                source_record_id=None,
            ),
        )

    monkeypatch.setattr(chat_route.service, "ask", return_no_evidence)

    response = chat_route.ask_chat(ChatAskRequest(raw_query="病假材料", debug=True))
    assert response.response_status == "fallback"

    hard_cases = _load_jsonl(tmp_path / "hard_cases.jsonl")
    assert len(hard_cases) == 1
    hc = hard_cases[0]
    assert hc["fallback_reason"] == "no_evidence"
    assert hc["issue_category"] == "retrieval_miss"
    assert "source_record_id" in hc
    assert "import_batch_id" in hc
    assert "unit_version" in hc
    assert "dynamic_query_key" in hc


def test_hard_case_issue_category_evidence_weak(monkeypatch, tmp_path) -> None:
    _configure_trace_storage(tmp_path)
    monkeypatch.setattr(chat_route, "settings", Settings(app_mode="demo"))

    def return_evidence_weak(payload, *, trace_id: str, debug_enabled: bool):
        return ChatAskResponse(
            response_status="fallback",
            trace_id=trace_id,
            answer="当前知识库中未命中足够依据。",
            citations=[],
            debug_info=DebugInfo(
                normalized_query=payload.raw_query.strip(),
                route_result="faq_qa_elastic",
                router_used="query_planner_local",
                retrieved_chunks=["unit-002"],
                route_confidence=None,
                retrieval_score=None,
                fusion_score=0.03,
                fallback_reason="evidence_below_threshold",
                retrieval_mode="hybrid_rerank",
                rerank_accept=False,
                rerank_score=0.22,
                evidence_confidence=0.15,
                evidence_span_count=0,
                reject_reason="evidence_below_threshold",
            ),
        )

    monkeypatch.setattr(chat_route.service, "ask", return_evidence_weak)

    response = chat_route.ask_chat(ChatAskRequest(raw_query="差旅标准", debug=True))
    assert response.response_status == "fallback"

    hard_cases = _load_jsonl(tmp_path / "hard_cases.jsonl")
    assert len(hard_cases) == 1
    assert hard_cases[0]["issue_category"] == "evidence_weak"


def test_hard_case_issue_category_extraction_drift(monkeypatch, tmp_path) -> None:
    _configure_trace_storage(tmp_path)
    monkeypatch.setattr(chat_route, "settings", Settings(app_mode="demo"))

    def return_extraction_drift(payload, *, trace_id: str, debug_enabled: bool):
        return ChatAskResponse(
            response_status="fallback",
            trace_id=trace_id,
            answer="当前知识库中未命中足够依据。",
            citations=[],
            debug_info=DebugInfo(
                normalized_query=payload.raw_query.strip(),
                route_result="faq_qa_elastic",
                router_used="query_planner_local",
                retrieved_chunks=["unit-003"],
                route_confidence=None,
                retrieval_score=None,
                fusion_score=0.01,
                fallback_reason="no_evidence",
                retrieval_mode="hybrid_rerank",
                rerank_accept=False,
                rerank_score=0.08,
                evidence_confidence=0.02,
                evidence_span_count=0,
                reject_reason="evidence_below_threshold",
                source_record_id="sr-travel-policy-002",
                import_batch_id="batch-2026-04-21",
                unit_version=2,
            ),
        )

    monkeypatch.setattr(chat_route.service, "ask", return_extraction_drift)

    response = chat_route.ask_chat(ChatAskRequest(raw_query="差旅报销", debug=True))

    hard_cases = _load_jsonl(tmp_path / "hard_cases.jsonl")
    assert len(hard_cases) == 1
    hc = hard_cases[0]
    assert hc["source_record_id"] == "sr-travel-policy-002"
    assert hc["import_batch_id"] == "batch-2026-04-21"
    assert hc["unit_version"] == 2
    assert hc["issue_category"] == "extraction_drift"


def test_hard_case_not_created_for_ok_response(tmp_path) -> None:
    _configure_trace_storage(tmp_path)

    response = chat_route.ask_chat(
        ChatAskRequest(raw_query="如何上传文档？", debug=True)
    )

    hard_cases = _load_jsonl(tmp_path / "hard_cases.jsonl")
    assert len(hard_cases) == 0


def test_feedback_upsert_enriches_hard_case_with_provenance(monkeypatch, tmp_path) -> None:
    _configure_trace_storage(tmp_path)
    monkeypatch.setattr(chat_route, "settings", Settings(app_mode="demo"))

    def return_with_provenance(payload, *, trace_id: str, debug_enabled: bool):
        return ChatAskResponse(
            response_status="ok",
            trace_id=trace_id,
            answer="请上传到 OA 系统即可。",
            citations=[],
            debug_info=DebugInfo(
                normalized_query=payload.raw_query.strip(),
                route_result="faq_qa_elastic",
                router_used="query_planner_local",
                retrieved_chunks=["unit-010"],
                route_confidence=0.9,
                retrieval_score=0.88,
                fusion_score=0.82,
                fallback_reason=None,
                retrieval_mode="hybrid_rerank",
                rerank_accept=True,
                rerank_score=0.78,
                evidence_confidence=0.7,
                evidence_span_count=1,
                source_record_id="sr-hr-doc-010",
                import_batch_id="batch-2026-04-22",
                unit_version=1,
            ),
        )

    monkeypatch.setattr(chat_route.service, "ask", return_with_provenance)

    ask_response = chat_route.ask_chat(
        ChatAskRequest(raw_query="上传文档", debug=True)
    )
    assert ask_response.response_status == "ok"

    hard_cases_before = _load_jsonl(tmp_path / "hard_cases.jsonl")
    assert len(hard_cases_before) == 0

    feedback_response = chat_route.submit_feedback(
        ChatFeedbackRequest(
            trace_id=ask_response.trace_id,
            raw_query="上传文档",
            answer_text=ask_response.answer,
            feedback_label="down",
            response_status=ask_response.response_status,
            retrieved_chunk_ids=["unit-010"],
            normalized_query=ask_response.debug_info.normalized_query,
            router_used=ask_response.debug_info.router_used,
            route_result=ask_response.debug_info.route_result,
            fallback_reason=ask_response.debug_info.fallback_reason,
        )
    )
    assert feedback_response.status == "recorded"

    hard_cases = _load_jsonl(tmp_path / "hard_cases.jsonl")
    assert len(hard_cases) == 1
    hc = hard_cases[0]
    assert hc["trace_id"] == ask_response.trace_id
    assert hc["user_feedback"] == "down"
    assert hc["source_record_id"] == "sr-hr-doc-010"
    assert hc["import_batch_id"] == "batch-2026-04-22"
    assert hc["unit_version"] == 1
    assert hc["issue_category"] == "extraction_drift"


def test_trace_replay_contains_phase3_fields(tmp_path) -> None:
    _configure_trace_storage(tmp_path)

    response = chat_route.ask_chat(
        ChatAskRequest(raw_query="如何上传文档？", debug=True)
    )

    replayed = chat_route.get_retrieval_trace(response.trace_id)
    assert "source_record_id" in replayed
    assert "import_batch_id" in replayed
    assert "unit_version" in replayed
    assert "dynamic_query_key" in replayed
