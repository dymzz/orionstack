import json
from pathlib import Path

from app.api.routes import chat as chat_route
from app.config.settings import Settings
from app.schemas.request import ChatAskRequest, ChatFeedbackRequest
from app.schemas.response import ChatAskResponse, DebugInfo


def _configure_hard_case_storage(tmp_path: Path) -> None:
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


def test_hard_case_is_created_from_negative_feedback(tmp_path) -> None:
    _configure_hard_case_storage(tmp_path)

    ask_response = chat_route.ask_chat(
        ChatAskRequest(raw_query="如何上传文档？", debug=True)
    )

    feedback_response = chat_route.submit_feedback(
        ChatFeedbackRequest(
            trace_id=ask_response.trace_id,
            raw_query="如何上传文档？",
            answer_text=ask_response.answer,
            feedback_label="down",
            response_status=ask_response.response_status,
            retrieved_chunk_ids=[ask_response.citations[0].citation_id],
            normalized_query=ask_response.debug_info.normalized_query
            if ask_response.debug_info is not None
            else "如何上传文档？",
            router_used=ask_response.debug_info.router_used
            if ask_response.debug_info is not None
            else None,
            route_result=ask_response.debug_info.route_result
            if ask_response.debug_info is not None
            else None,
            fallback_reason=ask_response.debug_info.fallback_reason
            if ask_response.debug_info is not None
            else None,
        )
    )

    assert feedback_response.status == "recorded"

    hard_cases = _load_jsonl(tmp_path / "hard_cases.jsonl")
    assert len(hard_cases) == 1
    hard_case = hard_cases[0]
    assert hard_case["trace_id"] == ask_response.trace_id
    assert hard_case["raw_query"] == "如何上传文档？"
    assert hard_case["normalized_query"] == "如何上传文档？"
    assert hard_case["router_used"] == ask_response.debug_info.router_used
    assert hard_case["user_feedback"] == "down"
    assert hard_case["fallback_reason"] is None
    assert hard_case["top_candidates"][0]["citation_id"] == ask_response.citations[0].citation_id
    assert hard_case["top_candidates"][0]["source_locator"] == ask_response.citations[0].source_locator
    assert hard_case["evidence_spans"][0]["text"] == ask_response.citations[0].snippet
    assert hard_case["created_at"]

    listed = chat_route.list_hard_cases(limit=10)
    assert len(listed["items"]) == 1
    assert listed["items"][0]["trace_id"] == ask_response.trace_id
    assert listed["items"][0]["user_feedback"] == "down"


def test_hard_case_is_created_from_no_evidence_response(monkeypatch, tmp_path) -> None:
    _configure_hard_case_storage(tmp_path)
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
                fallback_reason="no_evidence",
                retrieval_mode="hybrid_rerank",
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

    hard_cases = _load_jsonl(tmp_path / "hard_cases.jsonl")
    assert len(hard_cases) == 1
    hard_case = hard_cases[0]
    assert hard_case["trace_id"] == response.trace_id
    assert hard_case["raw_query"] == "病假材料"
    assert hard_case["normalized_query"] == "病假材料"
    assert hard_case["router_used"] == "query_planner_local"
    assert hard_case["fallback_reason"] == "no_evidence"
    assert hard_case["top_candidates"] == []
    assert hard_case["evidence_spans"] == []
    assert hard_case["user_feedback"] is None
    assert hard_case["created_at"]

    listed = chat_route.list_hard_cases(limit=10)
    assert len(listed["items"]) == 1
    assert listed["items"][0]["trace_id"] == response.trace_id
    assert listed["items"][0]["fallback_reason"] == "no_evidence"


def test_hard_case_feedback_upserts_existing_no_evidence_case(
    monkeypatch, tmp_path
) -> None:
    _configure_hard_case_storage(tmp_path)
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
                fallback_reason="no_evidence",
                retrieval_mode="hybrid_rerank",
                rerank_accept=False,
                rerank_score=0.09,
                evidence_confidence=0.0,
                evidence_span_count=0,
                reject_reason="evidence_below_threshold",
            ),
        )

    monkeypatch.setattr(chat_route.service, "ask", return_no_evidence)

    ask_response = chat_route.ask_chat(ChatAskRequest(raw_query="请假进度怎么看", debug=True))
    before_feedback = _load_jsonl(tmp_path / "hard_cases.jsonl")
    assert len(before_feedback) == 1
    assert before_feedback[0]["user_feedback"] is None

    feedback_response = chat_route.submit_feedback(
        ChatFeedbackRequest(
            trace_id=ask_response.trace_id,
            raw_query="请假进度怎么看",
            answer_text=ask_response.answer,
            feedback_label="down",
            response_status=ask_response.response_status,
            retrieved_chunk_ids=[],
            normalized_query=ask_response.debug_info.normalized_query
            if ask_response.debug_info is not None
            else "请假进度怎么看",
            router_used=ask_response.debug_info.router_used
            if ask_response.debug_info is not None
            else None,
            route_result=ask_response.debug_info.route_result
            if ask_response.debug_info is not None
            else None,
            fallback_reason=ask_response.debug_info.fallback_reason
            if ask_response.debug_info is not None
            else None,
        )
    )

    assert feedback_response.status == "recorded"

    hard_cases = _load_jsonl(tmp_path / "hard_cases.jsonl")
    assert len(hard_cases) == 1
    hard_case = hard_cases[0]
    assert hard_case["trace_id"] == ask_response.trace_id
    assert hard_case["raw_query"] == "请假进度怎么看"
    assert hard_case["router_used"] == "query_planner_local"
    assert hard_case["fallback_reason"] == "no_evidence"
    assert hard_case["user_feedback"] == "down"
    assert hard_case["normalized_query"] == "请假进度怎么看"
    assert hard_case["top_candidates"] == []
    assert hard_case["evidence_spans"] == []

    listed = chat_route.list_hard_cases(limit=10)
    assert len(listed["items"]) == 1
    assert listed["items"][0]["trace_id"] == ask_response.trace_id
    assert listed["items"][0]["user_feedback"] == "down"
