import json
from pathlib import Path

import pytest

from app.api.routes import chat as chat_route
from app.config.settings import Settings
from app.schemas.request import ChatAskRequest
from app.schemas.response import (
    ChatAskResponse,
    ClarificationInfo,
    ClarificationOption,
    DebugInfo,
    RetrievalCandidateSummary,
)
from conftest import fixture_case


def _configure_trace_storage(tmp_path: Path) -> None:
    chat_route.feedback_repository._path = tmp_path / "feedback_records.jsonl"
    chat_route.chat_record_repository._path = tmp_path / "chat_records.jsonl"
    chat_route.retrieval_trace_repository._path = tmp_path / "retrieval_traces.jsonl"
    chat_route.hard_cases_repository._path = tmp_path / "hard_cases.jsonl"


LEAVE_APPLY = fixture_case("leave_apply")
LEAVE_PROGRESS = fixture_case("leave_progress")
SICK_LEAVE_MATERIALS = fixture_case("sick_leave_materials")


def test_retrieval_trace_persists_and_replays_ok_record(tmp_path) -> None:
    _configure_trace_storage(tmp_path)

    ask_response = chat_route.ask_chat(
        ChatAskRequest(raw_query="如何上传文档？", debug=True)
    )

    trace_lines = (
        (tmp_path / "retrieval_traces.jsonl").read_text(encoding="utf-8").splitlines()
    )
    assert len(trace_lines) == 1
    trace_record = json.loads(trace_lines[0])
    assert trace_record["trace_id"] == ask_response.trace_id
    assert trace_record["raw_query"] == "如何上传文档？"
    assert trace_record["normalized_query"] == "如何上传文档？"
    assert trace_record["intent"] == "faq_qa"
    assert trace_record["router_used"] == ask_response.debug_info.router_used
    assert trace_record["final_status"] == "ok"
    assert trace_record["retrieved_chunks"] == [ask_response.citations[0].citation_id]
    assert trace_record["citations"][0]["source_locator"] == ask_response.citations[0].source_locator
    assert "retrieval_mode" in trace_record
    assert "retrieval_score" in trace_record
    assert "fusion_score" in trace_record
    assert "lexical_topk" in trace_record
    assert "vector_topk" in trace_record
    assert "rrf_topk" in trace_record
    assert "rerank_accept" in trace_record
    assert "reject_reason" in trace_record
    assert trace_record["created_at"]

    replayed_trace = chat_route.get_retrieval_trace(ask_response.trace_id)
    assert replayed_trace["trace_id"] == ask_response.trace_id
    assert replayed_trace["final_status"] == "ok"
    assert replayed_trace["citations"][0]["citation_id"] == ask_response.citations[0].citation_id


def test_retrieval_trace_persists_clarification_contract(monkeypatch, tmp_path) -> None:
    _configure_trace_storage(tmp_path)
    monkeypatch.setattr(chat_route, "settings", Settings(app_mode="demo"))

    def return_clarification(payload, *, trace_id: str, debug_enabled: bool):
        return ChatAskResponse(
            response_status="ok",
            trace_id=trace_id,
            answer="当前问题还不够具体，请先确认更接近哪一类规则。",
            citations=[],
            clarification=ClarificationInfo(
                clarification_required=True,
                question="您更想了解以下哪一项？",
                options=[
                    ClarificationOption(
                        option_id=LEAVE_APPLY["id"], label=LEAVE_APPLY["question"]
                    ),
                    ClarificationOption(
                        option_id=LEAVE_PROGRESS["id"], label=LEAVE_PROGRESS["question"]
                    ),
                ],
                conflict_reason="multiple_close_faq_candidates",
            ),
            debug_info=DebugInfo(
                normalized_query=payload.raw_query.strip(),
                route_result="faq_qa_elastic",
                router_used="query_planner_local",
                retrieved_chunks=[LEAVE_APPLY["id"], LEAVE_PROGRESS["id"]],
                route_confidence=None,
                retrieval_score=None,
                fusion_score=0.032258,
                fallback_reason="conflict_requires_clarification",
                retrieval_mode="clarification",
                lexical_topk=[
                    RetrievalCandidateSummary(
                        unit_id=LEAVE_APPLY["id"], score=2.4, source_kind="faq"
                    ),
                    RetrievalCandidateSummary(
                        unit_id=LEAVE_PROGRESS["id"], score=2.2, source_kind="faq"
                    ),
                ],
                vector_topk=[
                    RetrievalCandidateSummary(
                        unit_id=LEAVE_APPLY["id"], score=0.88, source_kind="faq"
                    ),
                    RetrievalCandidateSummary(
                        unit_id=LEAVE_PROGRESS["id"], score=0.86, source_kind="faq"
                    ),
                ],
                rrf_topk=[
                    RetrievalCandidateSummary(
                        unit_id=LEAVE_APPLY["id"], score=0.032258, source_kind="faq"
                    ),
                    RetrievalCandidateSummary(
                        unit_id=LEAVE_PROGRESS["id"], score=0.0319, source_kind="faq"
                    ),
                ],
                rerank_accept=True,
                rerank_score=0.73,
                evidence_confidence=0.5,
                evidence_span_count=1,
                reject_reason="multiple_close_faq_candidates",
            ),
        )

    monkeypatch.setattr(chat_route.service, "ask", return_clarification)

    response = chat_route.ask_chat(ChatAskRequest(raw_query="请假", debug=True))

    assert response.response_status == "ok"
    assert response.clarification is not None
    trace_record = chat_route.get_retrieval_trace(response.trace_id)
    assert trace_record["router_used"] == "query_planner_local"
    assert trace_record["retrieval_mode"] == "clarification"
    assert trace_record["retrieval_score"] is None
    assert trace_record["fusion_score"] == 0.032258
    assert trace_record["fallback_reason"] == "conflict_requires_clarification"
    assert [item["unit_id"] for item in trace_record["lexical_topk"]] == [
        LEAVE_APPLY["id"],
        LEAVE_PROGRESS["id"],
    ]
    assert [item["unit_id"] for item in trace_record["rrf_topk"]] == [
        LEAVE_APPLY["id"],
        LEAVE_PROGRESS["id"],
    ]
    assert trace_record["rerank_accept"] is True
    assert trace_record["rerank_score"] == 0.73
    assert trace_record["evidence_confidence"] == 0.5
    assert trace_record["evidence_span_count"] == 1
    assert trace_record["reject_reason"] == "multiple_close_faq_candidates"


def test_retrieval_trace_persists_no_evidence_contract(monkeypatch, tmp_path) -> None:
    _configure_trace_storage(tmp_path)
    monkeypatch.setattr(chat_route, "settings", Settings(app_mode="demo"))

    def return_no_evidence(payload, *, trace_id: str, debug_enabled: bool):
        return ChatAskResponse(
            response_status="fallback",
            trace_id=trace_id,
            answer="当前知识库中未命中足够依据，请尝试使用更明确的关键词提问。",
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
                lexical_topk=[
                    RetrievalCandidateSummary(
                        unit_id=SICK_LEAVE_MATERIALS["id"], score=2.1, source_kind="faq"
                    )
                ],
                vector_topk=[
                    RetrievalCandidateSummary(
                        unit_id=SICK_LEAVE_MATERIALS["id"], score=0.4, source_kind="faq"
                    )
                ],
                rrf_topk=[
                    RetrievalCandidateSummary(
                        unit_id=SICK_LEAVE_MATERIALS["id"], score=0.028, source_kind="faq"
                    )
                ],
                rerank_accept=False,
                rerank_score=0.11,
                evidence_confidence=0.05,
                evidence_span_count=0,
                reject_reason="evidence_below_threshold",
            ),
        )

    monkeypatch.setattr(chat_route.service, "ask", return_no_evidence)

    response = chat_route.ask_chat(ChatAskRequest(raw_query="病假材料", debug=True))

    assert response.response_status == "fallback"
    trace_record = chat_route.get_retrieval_trace(response.trace_id)
    assert trace_record["final_status"] == "fallback"
    assert trace_record["router_used"] == "query_planner_local"
    assert trace_record["fallback_reason"] == "no_evidence"
    assert trace_record["retrieval_mode"] == "hybrid_rerank"
    assert trace_record["retrieval_score"] is None
    assert trace_record["fusion_score"] == 0.028
    assert [item["unit_id"] for item in trace_record["lexical_topk"]] == [SICK_LEAVE_MATERIALS["id"]]
    assert [item["unit_id"] for item in trace_record["vector_topk"]] == [SICK_LEAVE_MATERIALS["id"]]
    assert [item["unit_id"] for item in trace_record["rrf_topk"]] == [SICK_LEAVE_MATERIALS["id"]]
    assert trace_record["rerank_accept"] is False
    assert trace_record["rerank_score"] == 0.11
    assert trace_record["evidence_confidence"] == 0.05
    assert trace_record["evidence_span_count"] == 0
    assert trace_record["reject_reason"] == "evidence_below_threshold"
