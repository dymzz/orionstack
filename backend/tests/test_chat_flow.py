import json
from pathlib import Path

import pytest

from app.api.routes import chat as chat_route
from app.api.routes import documents as documents_route
from app.config.settings import Settings
from app.schemas.request import ChatAskRequest, ChatFeedbackRequest
from app.services.chat_service import ChatService
from conftest import fixture_case, fixture_faq_map, fixture_path_for_faq_id
from fastapi.testclient import TestClient
from main import app

FIXTURE_DIRECT_ANSWER_IDS = tuple(
    fixture_case(case_name)["id"]
    for case_name in (
        "leave_apply",
        "sick_leave_materials",
        "leave_progress",
        "onboarding_day_one",
        "employment_certificate",
    )
)


def _configure_chat_record_storage(tmp_path: Path) -> None:
    chat_route.feedback_repository._path = tmp_path / "feedback_records.jsonl"
    chat_route.chat_record_repository._path = tmp_path / "chat_records.jsonl"
    chat_route.retrieval_trace_repository._path = tmp_path / "retrieval_traces.jsonl"
    chat_route.hard_cases_repository._path = tmp_path / "hard_cases.jsonl"


def _configure_shared_document_and_chat_storage(tmp_path: Path) -> None:
    _configure_chat_record_storage(tmp_path)
    documents_route.service._repository._meta_path = tmp_path / "documents.jsonl"
    documents_route.service._repository._upload_dir = tmp_path / "uploads"
    documents_route.service._chunk_repository._path = tmp_path / "chunks.jsonl"
    chat_route.service._chunk_repo._path = tmp_path / "chunks.jsonl"


def test_chat_service_returns_ok_for_known_faq_query(tmp_path) -> None:
    service = ChatService()
    service._chunk_repo._path = tmp_path / "chunks.jsonl"

    response = service.ask(
        ChatAskRequest(raw_query="如何上传文档？", debug=True),
        trace_id="trace-ok",
        debug_enabled=True,
    )

    assert response.response_status == "ok"
    assert response.trace_id == "trace-ok"
    assert response.answer
    assert len(response.citations) == 1
    assert response.clarification is None
    assert response.citations[0].citation_id == "faq-001"
    assert response.citations[0].source_label
    assert response.citations[0].source_locator
    assert response.citations[0].snippet
    assert response.debug_info is not None
    assert response.debug_info.retrieval_score is not None
    assert response.debug_info.fusion_score is None


def test_chat_service_prefers_document_chunk_before_faq(tmp_path) -> None:
    service = ChatService()
    service._chunk_repo._path = tmp_path / "chunks.jsonl"
    service._chunk_repo.save(
        document_id="doc-budget",
        filename="budget_guide.txt",
        chunks=["预算报表模板位于财务手册第一节，可在预算中心下载。"],
    )

    response = service.ask(
        ChatAskRequest(raw_query="如何查看预算报表模板？", debug=True),
        trace_id="trace-document-first",
        debug_enabled=True,
    )

    assert response.response_status == "ok"
    assert response.answer == "预算报表模板位于财务手册第一节，可在预算中心下载。"
    assert len(response.citations) == 1
    assert response.citations[0].citation_id == "doc-budget-chunk-1"
    assert response.citations[0].source_label == "budget_guide.txt"
    assert response.citations[0].source_locator == "document_id: doc-budget · chunk: 1"
    assert response.debug_info is not None
    assert response.debug_info.retrieved_chunks == ["doc-budget-chunk-1"]


def test_chat_service_limits_document_retrieval_to_selected_document_ids(
    tmp_path,
) -> None:
    service = ChatService()
    service._chunk_repo._path = tmp_path / "chunks.jsonl"
    service._chunk_repo.save(
        document_id="doc-budget",
        filename="budget_guide.txt",
        chunks=["预算报表模板位于财务手册第一节，可在预算中心下载。"],
    )
    service._chunk_repo.save(
        document_id="doc-policy",
        filename="policy.txt",
        chunks=["预算审批规则位于预算制度说明第二节。"],
    )

    response = service.ask(
        ChatAskRequest(
            raw_query="如何查看预算报表模板？",
            debug=True,
            document_ids=["doc-budget"],
        ),
        trace_id="trace-document-scope",
        debug_enabled=True,
    )

    assert response.response_status == "ok"
    assert response.answer == "预算报表模板位于财务手册第一节，可在预算中心下载。"
    assert len(response.citations) == 1
    assert response.citations[0].citation_id == "doc-budget-chunk-1"
    assert response.debug_info is not None
    assert response.debug_info.retrieved_chunks == ["doc-budget-chunk-1"]


def test_chat_service_returns_fallback_when_selected_documents_do_not_hit(
    tmp_path,
) -> None:
    service = ChatService()
    service._chunk_repo._path = tmp_path / "chunks.jsonl"
    service._chunk_repo.save(
        document_id="doc-budget",
        filename="budget_guide.txt",
        chunks=["预算报表模板位于财务手册第一节，可在预算中心下载。"],
    )
    service._chunk_repo.save(
        document_id="doc-policy",
        filename="policy.txt",
        chunks=["差旅报销流程说明位于行政制度第三节。"],
    )

    response = service.ask(
        ChatAskRequest(
            raw_query="如何查看预算报表模板？",
            debug=True,
            document_ids=["doc-policy"],
        ),
        trace_id="trace-document-scope-fallback",
        debug_enabled=True,
    )

    assert response.response_status == "fallback"
    assert response.citations == []
    assert response.debug_info is not None
    assert response.debug_info.fallback_reason == "retrieval_no_hit"


def test_chat_service_prefers_document_or_faq_when_weak_document_exists(
    tmp_path,
) -> None:
    service = ChatService()
    service._chunk_repo._path = tmp_path / "chunks.jsonl"
    service._chunk_repo.save(
        document_id="doc-weak",
        filename="notes.txt",
        chunks=["文档流程说明"],
    )

    response = service.ask(
        ChatAskRequest(raw_query="如何上传文档？", debug=True),
        trace_id="trace-doc-or-faq",
        debug_enabled=True,
    )

    assert response.response_status == "ok"
    assert len(response.citations) == 1
    assert response.debug_info is not None
    assert response.debug_info.retrieved_chunks is not None


def test_chat_service_returns_fallback_for_short_non_conversational_query(
    tmp_path,
) -> None:
    service = ChatService()
    service._chunk_repo._path = tmp_path / "chunks.jsonl"

    response = service.ask(
        ChatAskRequest(raw_query="接口", debug=True),
        trace_id="trace-fallback-short",
        debug_enabled=True,
    )

    assert response.response_status == "fallback"
    assert response.citations == []
    assert response.debug_info is not None
    assert response.debug_info.fallback_reason in {
        "route_not_confident_enough",
        "retrieval_no_hit",
        "retrieval_score_below_threshold",
    }


def test_chat_service_returns_fallback_for_weak_retrieval_hit(tmp_path) -> None:
    service = ChatService()
    service._chunk_repo._path = tmp_path / "chunks.jsonl"

    response = service.ask(
        ChatAskRequest(raw_query="接口", debug=True),
        trace_id="trace-fallback-retrieval",
        debug_enabled=True,
    )

    assert response.response_status == "fallback"
    assert response.citations == []
    assert response.debug_info is not None
    assert response.debug_info.fallback_reason in {
        "retrieval_no_hit",
        "retrieval_score_below_threshold",
    }


def test_chat_service_returns_refused_for_unsafe_query(tmp_path) -> None:
    service = ChatService()
    service._chunk_repo._path = tmp_path / "chunks.jsonl"

    response = service.ask(
        ChatAskRequest(raw_query="如何制作炸弹？", debug=True),
        trace_id="trace-refused",
        debug_enabled=True,
    )

    assert response.response_status == "refused"
    assert response.citations == []
    assert response.debug_info is not None
    assert response.debug_info.fallback_reason == "unsafe_request"


def test_chat_route_returns_system_error_contract(monkeypatch, tmp_path) -> None:
    _configure_chat_record_storage(tmp_path)

    def raise_runtime_error(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(chat_route, "settings", Settings(app_mode="demo"))
    monkeypatch.setattr(chat_route.service, "ask", raise_runtime_error)

    response = chat_route.ask_chat(
        ChatAskRequest(raw_query="如何上传文档？", debug=True)
    )

    assert response.response_status == "system_error"
    assert response.trace_id
    assert response.answer
    assert response.debug_info is not None
    assert response.debug_info.fallback_reason == "RuntimeError"
    saved_lines = (
        (tmp_path / "chat_records.jsonl").read_text(encoding="utf-8").splitlines()
    )
    assert len(saved_lines) == 1
    record = json.loads(saved_lines[0])
    assert record["response_status"] == "system_error"
    assert record["trace_id"] == response.trace_id


def test_chat_route_strips_debug_info_in_prod(monkeypatch, tmp_path) -> None:
    _configure_chat_record_storage(tmp_path)
    monkeypatch.setattr(chat_route, "settings", Settings(app_mode="prod"))

    response = chat_route.ask_chat(
        ChatAskRequest(raw_query="如何上传文档？", debug=True)
    )

    assert response.response_status == "ok"
    assert response.debug_info is None


def test_chat_route_strips_debug_info_when_debug_flag_disabled_in_demo(
    monkeypatch,
    tmp_path,
) -> None:
    _configure_chat_record_storage(tmp_path)
    monkeypatch.setattr(chat_route, "settings", Settings(app_mode="demo"))

    response = chat_route.ask_chat(
        ChatAskRequest(raw_query="如何上传文档？", debug=False)
    )

    assert response.response_status == "ok"
    assert response.debug_info is None


def test_chat_route_records_feedback(tmp_path) -> None:
    _configure_chat_record_storage(tmp_path)
    ask_response = chat_route.ask_chat(
        ChatAskRequest(raw_query="如何上传文档？", debug=True)
    )

    response = chat_route.submit_feedback(
        ChatFeedbackRequest(
            trace_id=ask_response.trace_id,
            raw_query="如何上传文档？",
            answer_text="请在文档页面点击上传按钮。",
            feedback_label="up",
            response_status="ok",
            retrieved_chunk_ids=["faq-001"],
            normalized_query="如何上传文档？",
            router_used="rule_parser",
            route_result="faq_qa",
        )
    )

    assert response.status == "recorded"
    saved_lines = (
        (tmp_path / "feedback_records.jsonl").read_text(encoding="utf-8").splitlines()
    )
    assert len(saved_lines) == 1
    record = json.loads(saved_lines[0])
    assert record["trace_id"] == ask_response.trace_id
    assert record["feedback_label"] == "up"
    assert record["retrieved_chunk_ids"] == ["faq-001"]
    assert record["response_status"] == "ok"
    assert record["created_at"]

    chat_record_lines = (
        (tmp_path / "chat_records.jsonl").read_text(encoding="utf-8").splitlines()
    )
    assert len(chat_record_lines) == 1
    chat_record = json.loads(chat_record_lines[0])
    assert chat_record["trace_id"] == ask_response.trace_id
    assert chat_record["feedback_label"] == "up"
    assert chat_record["feedback_created_at"]

    feedback_records_response = chat_route.list_feedback_records(limit=10)
    assert len(feedback_records_response.items) == 1
    assert feedback_records_response.items[0].trace_id == ask_response.trace_id
    assert feedback_records_response.items[0].feedback_label == "up"


def test_chat_route_persists_retrieval_trace_and_replays_by_trace_id(
    tmp_path,
) -> None:
    _configure_chat_record_storage(tmp_path)

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
    assert trace_record["final_status"] == "ok"
    assert "retrieval_mode" in trace_record
    assert "retrieval_score" in trace_record
    assert "fusion_score" in trace_record
    assert trace_record["retrieval_mode"] is None
    assert trace_record["lexical_topk"] == []
    assert trace_record["vector_topk"] == []
    assert trace_record["rrf_topk"] == []
    assert trace_record["rerank_accept"] is None
    assert trace_record["rerank_score"] is None
    assert trace_record["evidence_confidence"] is None
    assert trace_record["evidence_span_count"] is None
    assert trace_record["reject_reason"] is None
    assert trace_record["retrieved_chunks"] == [ask_response.citations[0].citation_id]
    assert trace_record["citations"][0]["citation_id"] == ask_response.citations[0].citation_id
    assert trace_record["created_at"]

    replayed_trace = chat_route.get_retrieval_trace(ask_response.trace_id)
    assert replayed_trace["trace_id"] == ask_response.trace_id
    assert (
        replayed_trace["citations"][0]["source_locator"]
        == ask_response.citations[0].source_locator
    )


def test_chat_route_preserves_clarification_contract(monkeypatch, tmp_path) -> None:
    _configure_chat_record_storage(tmp_path)

    def return_clarification(payload, *, trace_id: str, debug_enabled: bool):
        from app.schemas.response import (
            ChatAskResponse,
            ClarificationInfo,
            ClarificationOption,
            DebugInfo,
        )

        return ChatAskResponse(
            response_status="ok",
            trace_id=trace_id,
            answer="当前问题还不够具体，请先确认更接近哪一类规则。",
            citations=[],
            clarification=ClarificationInfo(
                clarification_required=True,
                question="您想了解哪一种请假规则？",
                options=[
                    ClarificationOption(
                        option_id="annual_leave",
                        label="年假申请流程",
                    ),
                    ClarificationOption(
                        option_id="sick_leave",
                        label="病假材料要求",
                    ),
                ],
                conflict_reason="short_generic_query",
            ),
            debug_info=DebugInfo(
                normalized_query=payload.raw_query.strip(),
                route_result="faq_qa_elastic",
                router_used="query_planner_local",
                retrieved_chunks=[],
                route_confidence=None,
                retrieval_score=None,
                fusion_score=0.032258,
                fallback_reason="conflict_requires_clarification",
                retrieval_mode="clarification",
                rerank_accept=True,
                rerank_score=0.73,
                evidence_confidence=0.5,
                evidence_span_count=1,
                reject_reason="multiple_close_faq_candidates",
            ),
        )

    monkeypatch.setattr(chat_route, "settings", Settings(app_mode="demo"))
    monkeypatch.setattr(chat_route.service, "ask", return_clarification)

    response = chat_route.ask_chat(ChatAskRequest(raw_query="请假", debug=True))

    assert response.response_status == "ok"
    assert response.clarification is not None
    assert response.clarification.clarification_required is True
    assert response.clarification.question == "您想了解哪一种请假规则？"
    assert [option.label for option in response.clarification.options] == [
        "年假申请流程",
        "病假材料要求",
    ]
    assert response.debug_info is not None
    assert response.debug_info.fallback_reason == "conflict_requires_clarification"
    trace_lines = (
        (tmp_path / "retrieval_traces.jsonl").read_text(encoding="utf-8").splitlines()
    )
    trace_record = json.loads(trace_lines[0])
    assert trace_record["retrieval_mode"] == "clarification"
    assert trace_record["fusion_score"] == 0.032258
    assert trace_record["lexical_topk"] == []
    assert trace_record["vector_topk"] == []
    assert trace_record["rrf_topk"] == []
    assert trace_record["rerank_accept"] is True
    assert trace_record["rerank_score"] == 0.73
    assert trace_record["evidence_confidence"] == 0.5
    assert trace_record["evidence_span_count"] == 1
    assert trace_record["reject_reason"] == "multiple_close_faq_candidates"


def test_chat_route_records_hard_case_for_negative_feedback(tmp_path) -> None:
    _configure_chat_record_storage(tmp_path)

    ask_response = chat_route.ask_chat(
        ChatAskRequest(raw_query="如何上传文档？", debug=True)
    )

    chat_route.submit_feedback(
        ChatFeedbackRequest(
            trace_id=ask_response.trace_id,
            raw_query="如何上传文档？",
            answer_text=ask_response.answer,
            feedback_label="down",
            response_status="ok",
            retrieved_chunk_ids=[ask_response.citations[0].citation_id],
            normalized_query="如何上传文档？",
            router_used="rule_parser",
            route_result="faq_qa",
        )
    )

    hard_case_lines = (
        (tmp_path / "hard_cases.jsonl").read_text(encoding="utf-8").splitlines()
    )
    assert len(hard_case_lines) == 1
    hard_case = json.loads(hard_case_lines[0])
    assert hard_case["trace_id"] == ask_response.trace_id
    assert hard_case["user_feedback"] == "down"
    assert hard_case["raw_query"] == "如何上传文档？"
    assert hard_case["top_candidates"][0]["citation_id"] == ask_response.citations[0].citation_id
    assert hard_case["evidence_spans"][0]["text"]

    listed = chat_route.list_hard_cases(limit=10)
    assert len(listed["items"]) == 1
    assert listed["items"][0]["trace_id"] == ask_response.trace_id


def test_chat_route_records_hard_case_for_no_evidence_fallback(
    monkeypatch, tmp_path
) -> None:
    _configure_chat_record_storage(tmp_path)

    def return_no_evidence(payload, *, trace_id: str, debug_enabled: bool):
        from app.schemas.response import ChatAskResponse, DebugInfo

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
                rerank_accept=False,
                rerank_score=0.11,
                evidence_confidence=0.05,
                evidence_span_count=0,
                reject_reason="evidence_below_threshold",
            ),
        )

    monkeypatch.setattr(chat_route, "settings", Settings(app_mode="demo"))
    monkeypatch.setattr(chat_route.service, "ask", return_no_evidence)

    response = chat_route.ask_chat(ChatAskRequest(raw_query="请假", debug=True))

    assert response.response_status == "fallback"
    hard_case_lines = (
        (tmp_path / "hard_cases.jsonl").read_text(encoding="utf-8").splitlines()
    )
    assert len(hard_case_lines) == 1
    hard_case = json.loads(hard_case_lines[0])
    assert hard_case["trace_id"] == response.trace_id
    assert hard_case["fallback_reason"] == "no_evidence"
    assert hard_case["raw_query"] == "请假"

    replayed_trace = chat_route.get_retrieval_trace(response.trace_id)
    assert replayed_trace["final_status"] == "fallback"
    assert replayed_trace["fallback_reason"] == "no_evidence"
    assert replayed_trace["retrieval_mode"] == "hybrid_rerank"
    assert replayed_trace["fusion_score"] == 0.028
    assert replayed_trace["lexical_topk"] == []
    assert replayed_trace["vector_topk"] == []
    assert replayed_trace["rrf_topk"] == []
    assert replayed_trace["rerank_accept"] is False
    assert replayed_trace["rerank_score"] == 0.11
    assert replayed_trace["evidence_confidence"] == 0.05
    assert replayed_trace["evidence_span_count"] == 0
    assert replayed_trace["reject_reason"] == "evidence_below_threshold"


def test_chat_route_lists_recent_records_in_demo(tmp_path, monkeypatch) -> None:
    _configure_chat_record_storage(tmp_path)
    monkeypatch.setattr(chat_route, "settings", Settings(app_mode="demo"))

    first_response = chat_route.ask_chat(
        ChatAskRequest(raw_query="如何上传文档？", debug=True)
    )
    second_response = chat_route.ask_chat(
        ChatAskRequest(raw_query="如何制作炸弹？", debug=True)
    )
    third_response = chat_route.ask_chat(ChatAskRequest(raw_query="如何", debug=True))

    records_response = chat_route.list_chat_records(limit=10)
    feedback_response = chat_route.list_feedback_records(limit=10)

    assert [item.trace_id for item in records_response.items] == [
        third_response.trace_id,
        second_response.trace_id,
        first_response.trace_id,
    ]
    assert records_response.items[0].response_status in {"ok", "fallback"}
    assert records_response.items[1].response_status == "refused"
    assert records_response.items[2].response_status == "ok"
    assert feedback_response.items == []


def test_chat_route_hides_record_endpoints_in_prod(monkeypatch) -> None:
    monkeypatch.setattr(chat_route, "settings", Settings(app_mode="prod"))

    try:
        chat_route.list_chat_records(limit=10)
    except Exception as error:
        assert getattr(error, "status_code", None) == 404
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("expected record endpoint to be hidden in prod")

    try:
        chat_route.list_feedback_records(limit=10)
    except Exception as error:
        assert getattr(error, "status_code", None) == 404
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("expected feedback endpoint to be hidden in prod")

    try:
        chat_route.get_retrieval_trace("trace-missing")
    except Exception as error:
        assert getattr(error, "status_code", None) == 404
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("expected trace replay endpoint to be hidden in prod")

    try:
        chat_route.list_hard_cases(limit=10)
    except Exception as error:
        assert getattr(error, "status_code", None) == 404
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("expected hard cases endpoint to be hidden in prod")


def test_chat_record_repo_truncates_oldest_records(tmp_path) -> None:
    from app.storage.repositories.chat_record_repo import ChatRecordRepository

    repo = ChatRecordRepository(max_count=3)
    repo._path = tmp_path / "chat_records.jsonl"

    for index in range(5):
        repo.save(
            {
                "trace_id": f"trace-{index}",
                "raw_query": f"q{index}",
                "response_status": "ok",
                "retrieved_chunk_ids": [],
            }
        )

    lines = (tmp_path / "chat_records.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3
    records = [json.loads(line) for line in lines if line.strip()]
    assert records[0]["trace_id"] == "trace-2"
    assert records[2]["trace_id"] == "trace-4"


def test_feedback_repo_truncates_oldest_records(tmp_path) -> None:
    from app.storage.repositories.feedback_repo import FeedbackRepository

    repo = FeedbackRepository(max_count=3)
    repo._path = tmp_path / "feedback_records.jsonl"

    for index in range(5):
        repo.save(
            {
                "trace_id": f"trace-{index}",
                "raw_query": f"q{index}",
                "feedback_label": "up",
                "response_status": "ok",
            }
        )

    lines = (
        (tmp_path / "feedback_records.jsonl").read_text(encoding="utf-8").splitlines()
    )
    assert len(lines) == 3
    records = [json.loads(line) for line in lines if line.strip()]
    assert records[0]["trace_id"] == "trace-2"
    assert records[2]["trace_id"] == "trace-4"


def test_cors_origins_default_includes_dev_origins() -> None:
    default_settings = Settings()
    assert "http://localhost:5173" in default_settings.cors_origins
    assert "http://127.0.0.1:5173" in default_settings.cors_origins


def test_cors_origins_can_be_configured_via_env(monkeypatch) -> None:
    monkeypatch.setenv(
        "ORIONSTACK_CORS_ORIGINS", "https://example.com,https://app.example.com"
    )
    custom_settings = Settings()
    assert custom_settings.cors_origins == (
        "https://example.com",
        "https://app.example.com",
    )


def test_cors_origins_empty_env_falls_back_to_defaults(monkeypatch) -> None:
    monkeypatch.delenv("ORIONSTACK_CORS_ORIGINS", raising=False)
    default_settings = Settings()
    assert default_settings.cors_origins == (
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    )


def test_record_repo_does_not_truncate_when_max_count_is_zero(tmp_path) -> None:
    from app.storage.repositories.chat_record_repo import ChatRecordRepository

    repo = ChatRecordRepository(max_count=0)
    repo._path = tmp_path / "chat_records.jsonl"

    for index in range(5):
        repo.save(
            {
                "trace_id": f"trace-{index}",
                "raw_query": f"q{index}",
                "response_status": "ok",
                "retrieved_chunk_ids": [],
            }
        )

    lines = (tmp_path / "chat_records.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 5


def test_tokenizer_generates_bigrams_for_chinese_queries() -> None:
    from app.retrieval.retriever import Retriever

    tokens = Retriever._tokenize("怎么请假")
    assert "怎么请假" in tokens
    assert "怎么" in tokens
    assert "请假" in tokens

    tokens_short = Retriever._tokenize("请假")
    assert "请假" in tokens_short

    tokens_multi = Retriever._tokenize("如何 申请 年假")
    assert "如何" in tokens_multi
    assert "申请" in tokens_multi
    assert "年假" in tokens_multi


def test_short_chinese_query_hits_document_chunk(tmp_path) -> None:
    service = ChatService()
    service._chunk_repo._path = tmp_path / "chunks.jsonl"
    service._chunk_repo.save(
        document_id="doc-hr",
        filename="hr_faq.md",
        chunks=["请假审批进度可在请假申请记录中查看。"],
    )

    response = service.ask(
        ChatAskRequest(raw_query="请假", debug=True),
        trace_id="trace-short-chinese",
        debug_enabled=True,
    )

    assert response.response_status == "ok"
    assert "请假" in response.answer
    assert len(response.citations) == 1


@pytest.mark.parametrize(
    "faq_id",
    FIXTURE_DIRECT_ANSWER_IDS,
)
def test_chat_route_returns_structured_answers_for_uploaded_hr_faq_seed_queries(
    tmp_path,
    faq_id: str,
) -> None:
    faq_item = fixture_faq_map()[faq_id]
    _configure_shared_document_and_chat_storage(tmp_path)

    fixture_path = fixture_path_for_faq_id(faq_id)
    client = TestClient(app)
    upload_response = client.post(
        "/api/documents/upload",
        files={
            "file": (
                fixture_path.name,
                fixture_path.read_bytes(),
                "text/markdown",
            )
        },
    )

    assert upload_response.status_code == 200

    ask_response = client.post(
        "/api/chat/ask",
        json={"raw_query": faq_item["question"], "debug": True},
    )

    assert ask_response.status_code == 200
    payload = ask_response.json()
    assert payload["response_status"] == "ok"
    assert faq_item["answer"] == payload["answer"]
    assert len(payload["citations"]) == 1
    assert payload["citations"][0]["citation_id"] == faq_item["id"]
    assert payload["citations"][0]["source_label"] == faq_item["source_label"]
    assert payload["citations"][0]["source_locator"] == faq_item["source_locator"]
    assert faq_item["snippet"][:12] in payload["citations"][0]["snippet"]
