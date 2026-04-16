import json
from pathlib import Path
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.api.routes import chat as chat_route
from app.config.settings import Settings
from app.schemas.request import ChatAskRequest, ChatFeedbackRequest
from app.services.chat_service import ChatService


def _configure_chat_record_storage(tmp_path: Path) -> None:
    chat_route.feedback_repository._path = tmp_path / "feedback_records.jsonl"
    chat_route.chat_record_repository._path = tmp_path / "chat_records.jsonl"


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
    assert response.citations[0].citation_id == "faq-001"
    assert response.citations[0].source_label
    assert response.citations[0].source_locator
    assert response.citations[0].snippet
    assert response.debug_info is not None
    assert response.debug_info.retrieval_score is not None


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


def test_chat_service_falls_back_to_faq_when_document_hit_is_weak(tmp_path) -> None:
    service = ChatService()
    service._chunk_repo._path = tmp_path / "chunks.jsonl"
    service._chunk_repo.save(
        document_id="doc-weak",
        filename="notes.txt",
        chunks=["文档流程说明"],
    )

    response = service.ask(
        ChatAskRequest(raw_query="如何上传文档？", debug=True),
        trace_id="trace-faq-fallback",
        debug_enabled=True,
    )

    assert response.response_status == "ok"
    assert len(response.citations) == 1
    assert response.citations[0].citation_id == "faq-001"
    assert response.citations[0].source_label == "Mock FAQ"
    assert response.debug_info is not None
    assert response.debug_info.retrieved_chunks == ["faq-001"]


def test_chat_service_returns_fallback_for_low_confidence_route(tmp_path) -> None:
    service = ChatService()
    service._chunk_repo._path = tmp_path / "chunks.jsonl"

    response = service.ask(
        ChatAskRequest(raw_query="如何", debug=True),
        trace_id="trace-fallback-route",
        debug_enabled=True,
    )

    assert response.response_status == "fallback"
    assert response.citations == []
    assert response.debug_info is not None
    assert response.debug_info.fallback_reason == "route_not_confident_enough"


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
    assert records_response.items[0].response_status == "fallback"
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
