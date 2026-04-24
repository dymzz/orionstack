import json
from pathlib import Path

from scripts.audit_provider_bad_cases import (
    audit_category,
    build_audit_report,
    router_names_for_providers,
)


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n",
        encoding="utf-8",
    )


def test_router_names_for_providers_keeps_provider_boundary_generic() -> None:
    routers = router_names_for_providers(
        {"openai_compatible", "llama_cpp"},
        include_local=True,
    )

    assert routers == {
        "query_planner_openai_compatible",
        "query_planner_llama_cpp",
        "query_planner_local",
    }


def test_audit_category_maps_core_failure_layers() -> None:
    assert audit_category({"fallback_reason": "no_evidence"}) == "corpus_gap"
    assert (
        audit_category({"fallback_reason": "evidence_below_threshold"})
        == "evidence_threshold"
    )
    assert (
        audit_category({"fallback_reason": "conflict_requires_clarification"})
        == "clarification_boundary"
    )
    assert (
        audit_category({"fallback_reason": "route_not_confident_enough"})
        == "planner_boundary"
    )
    assert audit_category({"source_record_id": "sr-001"}) == "extraction_drift"
    assert audit_category({"user_feedback": "down"}) == "negative_feedback_review"


def test_build_audit_report_filters_provider_routers_and_merges_hard_cases(
    tmp_path,
) -> None:
    root = tmp_path
    _write_jsonl(
        root
        / "backend"
        / "app"
        / "storage"
        / "retrieval_traces"
        / "retrieval_traces.jsonl",
        [
            {
                "trace_id": "ok-openai",
                "raw_query": "如何上传文档",
                "normalized_query": "如何上传文档",
                "router_used": "query_planner_openai_compatible",
                "final_status": "ok",
                "fallback_reason": None,
                "retrieval_mode": "hybrid_rerank",
                "retrieved_chunks": ["faq-001"],
                "created_at": "2026-04-22T10:00:00+00:00",
            },
            {
                "trace_id": "miss-openai",
                "raw_query": "演示资料在哪里找",
                "normalized_query": "演示资料在哪里找",
                "router_used": "query_planner_openai_compatible",
                "final_status": "fallback",
                "fallback_reason": "no_evidence",
                "retrieval_mode": "hybrid_rerank",
                "retrieved_chunks": [],
                "created_at": "2026-04-22T10:01:00+00:00",
            },
            {
                "trace_id": "closed-openai",
                "raw_query": "演示资料在哪里找",
                "normalized_query": "演示资料在哪里找",
                "router_used": "query_planner_openai_compatible",
                "final_status": "ok",
                "fallback_reason": None,
                "retrieval_mode": "hybrid_rerank",
                "retrieved_chunks": ["sales-faq-003"],
                "created_at": "2026-04-22T10:02:00+00:00",
            },
            {
                "trace_id": "clarify-llama",
                "raw_query": "账号",
                "normalized_query": "账号",
                "router_used": "query_planner_llama_cpp",
                "final_status": "ok",
                "fallback_reason": "conflict_requires_clarification",
                "retrieval_mode": "clarification",
                "retrieved_chunks": ["it-faq-001", "it-faq-002"],
                "created_at": "2026-04-22T10:03:00+00:00",
            },
            {
                "trace_id": "local-miss",
                "raw_query": "请假进度",
                "normalized_query": "请假进度",
                "router_used": "query_planner_local",
                "final_status": "fallback",
                "fallback_reason": "no_evidence",
                "retrieval_mode": "hybrid_rerank",
                "retrieved_chunks": [],
                "created_at": "2026-04-22T10:04:00+00:00",
            },
        ],
    )
    _write_jsonl(
        root / "backend" / "app" / "storage" / "hard_cases" / "hard_cases.jsonl",
        [
            {
                "trace_id": "ok-openai",
                "raw_query": "如何上传文档",
                "router_used": "query_planner_openai_compatible",
                "fallback_reason": None,
                "user_feedback": "down",
                "created_at": "2026-04-22T10:00:30+00:00",
            },
            {
                "trace_id": "miss-openai",
                "raw_query": "演示资料在哪里找",
                "normalized_query": "演示资料在哪里找",
                "router_used": "query_planner_openai_compatible",
                "fallback_reason": "no_evidence",
                "issue_category": "retrieval_miss",
                "created_at": "2026-04-22T10:01:30+00:00",
            },
            {
                "trace_id": "local-miss",
                "raw_query": "请假进度",
                "router_used": "query_planner_local",
                "fallback_reason": "no_evidence",
                "issue_category": "retrieval_miss",
            },
        ],
    )

    report = build_audit_report(
        root=root,
        router_names={
            "query_planner_openai_compatible",
            "query_planner_llama_cpp",
        },
    )

    assert report["trace_count"] == 4
    assert report["hard_case_count"] == 2
    assert report["bad_trace_count"] == 1
    assert report["status"] == {"ok": 3, "fallback": 1}
    assert report["fallback_reason"] == {
        "no_evidence": 1,
        "conflict_requires_clarification": 1,
    }
    assert report["audit_category"] == {
        "negative_feedback_review": 1,
        "corpus_gap": 1,
    }
    assert report["audit_resolution"] == {
        "open": 1,
        "closed_by_later_success": 1,
    }
    assert report["bad_traces"][0]["audit_resolution"] == "closed_by_later_success"
    assert report["hard_cases"][1]["audit_resolution"] == "closed_by_later_success"
    assert report["hard_cases"][1]["retrieval_mode"] == "hybrid_rerank"
    assert report["hard_cases"][1]["retrieved_chunks"] == []
