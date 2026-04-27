from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


DEFAULT_PROVIDER_NAMES = (
    "openai_compatible",
    "llama_cpp",
    # Historical compatibility alias. Keep it visible in audit output so old
    # traces remain reviewable without making Qwen the architectural target.
    "qwen_api",
)

BAD_TRACE_FALLBACK_REASONS = {
    "no_evidence",
    "retrieval_no_hit",
    "retrieval_score_below_threshold",
    "evidence_below_threshold",
    "stale_knowledge",
    "lexical_backend_error",
    "vector_backend_error",
    "ConnectionTimeout",
    "PlannerTimeout",
    "PlannerHttpError",
    "PlannerAuthError",
    "PlannerResponseFormatError",
}

ISSUE_TO_AUDIT_CATEGORY = {
    "retrieval_miss": "corpus_gap",
    "evidence_weak": "evidence_threshold",
    "extraction_drift": "extraction_drift",
    "retrieval_ambiguous": "clarification_boundary",
    "routing_mismatch": "planner_boundary",
    "freshness_stale": "freshness_stale",
}


def parse_csv(raw: str) -> set[str]:
    return {item.strip() for item in raw.split(",") if item.strip()}


def router_names_for_providers(
    provider_names: set[str],
    *,
    include_local: bool = False,
) -> set[str]:
    router_names = {f"query_planner_{name}" for name in provider_names}
    if include_local:
        router_names.add("query_planner_local")
    return router_names


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def trace_path(root: Path) -> Path:
    return root / "backend" / "app" / "storage" / "retrieval_traces" / "retrieval_traces.jsonl"


def hard_case_path(root: Path) -> Path:
    return root / "backend" / "app" / "storage" / "hard_cases" / "hard_cases.jsonl"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def is_bad_trace(record: dict[str, Any]) -> bool:
    if record.get("final_status") not in (None, "ok"):
        return True
    return record.get("fallback_reason") in BAD_TRACE_FALLBACK_REASONS


def audit_category(record: dict[str, Any]) -> str:
    issue_category = record.get("issue_category")
    if isinstance(issue_category, str) and issue_category in ISSUE_TO_AUDIT_CATEGORY:
        return ISSUE_TO_AUDIT_CATEGORY[issue_category]

    if record.get("source_record_id"):
        return "extraction_drift"

    fallback_reason = record.get("fallback_reason")
    reject_reason = record.get("reject_reason")
    if fallback_reason in ("no_evidence", "retrieval_no_hit"):
        return "corpus_gap"
    if fallback_reason in ("evidence_below_threshold", "retrieval_score_below_threshold"):
        return "evidence_threshold"
    if reject_reason == "evidence_below_threshold":
        return "evidence_threshold"
    if fallback_reason == "conflict_requires_clarification":
        return "clarification_boundary"
    if fallback_reason == "route_not_confident_enough":
        return "planner_boundary"
    if fallback_reason == "stale_knowledge":
        return "freshness_stale"
    if fallback_reason in {
        "ConnectionTimeout",
        "PlannerTimeout",
        "PlannerHttpError",
        "PlannerAuthError",
        "PlannerResponseFormatError",
    }:
        return "provider_health"
    if fallback_reason in ("lexical_backend_error", "vector_backend_error"):
        return "retrieval_backend"
    if record.get("user_feedback") == "down":
        return "negative_feedback_review"
    if record.get("final_status") == "system_error":
        return "system_error"
    return "unknown"


def build_audit_report(
    *,
    root: Path,
    router_names: set[str],
) -> dict[str, Any]:
    traces = load_jsonl(trace_path(root))
    hard_cases = load_jsonl(hard_case_path(root))
    trace_by_id = {str(record.get("trace_id", "")): record for record in traces}

    filtered_traces = [
        record for record in traces if record.get("router_used") in router_names
    ]
    filtered_hard_cases = [
        record for record in hard_cases if record.get("router_used") in router_names
    ]
    traces_by_query = _group_traces_by_query(filtered_traces)
    bad_traces = [
        annotate_resolution(record, traces_by_query)
        for record in filtered_traces
        if is_bad_trace(record)
    ]
    merged_hard_cases = [
        annotate_resolution(
            _merge_hard_case_with_trace(hard_case, trace_by_id),
            traces_by_query,
        )
        for hard_case in filtered_hard_cases
    ]
    hard_case_trace_ids = {
        str(record.get("trace_id", "")) for record in merged_hard_cases
    }
    standalone_bad_traces = [
        record
        for record in bad_traces
        if str(record.get("trace_id", "")) not in hard_case_trace_ids
    ]
    review_records = [*standalone_bad_traces, *merged_hard_cases]

    return {
        "router_names": sorted(router_names),
        "trace_count": len(filtered_traces),
        "hard_case_count": len(filtered_hard_cases),
        "bad_trace_count": len(bad_traces),
        "status": dict(Counter(record.get("final_status") for record in filtered_traces)),
        "fallback_reason": dict(
            Counter(
                record.get("fallback_reason")
                for record in filtered_traces
                if record.get("fallback_reason") is not None
            )
        ),
        "retrieval_mode": dict(
            Counter(record.get("retrieval_mode") for record in filtered_traces)
        ),
        "audit_category": dict(Counter(audit_category(record) for record in review_records)),
        "audit_resolution": dict(
            Counter(record.get("audit_resolution", "open") for record in review_records)
        ),
        "bad_traces": bad_traces,
        "hard_cases": merged_hard_cases,
    }


def render_audit_report(report: dict[str, Any], *, limit: int = 20) -> str:
    lines = [
        "[orionstack] provider bad-case audit",
        f"[orionstack] router_used={report['router_names']}",
        (
            f"[orionstack] traces={report['trace_count']} "
            f"hard_cases={report['hard_case_count']}"
        ),
        f"[orionstack] status={report['status']}",
        f"[orionstack] fallback_reason={report['fallback_reason']}",
        f"[orionstack] retrieval_mode={report['retrieval_mode']}",
        f"[orionstack] audit_category={report['audit_category']}",
        f"[orionstack] audit_resolution={report['audit_resolution']}",
        "",
        f"[orionstack] candidate bad traces ({report['bad_trace_count']})",
    ]
    bad_traces = report["bad_traces"]
    for record in bad_traces[:limit]:
        lines.append(format_record(record, source="trace"))
    if len(bad_traces) > limit:
        lines.append(f"[orionstack] ... truncated {len(bad_traces) - limit} more")

    hard_cases = report["hard_cases"]
    lines.extend(["", f"[orionstack] hard cases on same router ({len(hard_cases)})"])
    for record in hard_cases[:limit]:
        lines.append(format_record(record, source="hard_case"))
    if len(hard_cases) > limit:
        lines.append(f"[orionstack] ... truncated {len(hard_cases) - limit} more")

    return "\n".join(lines)


def format_record(record: dict[str, Any], *, source: str) -> str:
    query = record.get("raw_query", "")
    trace_id = record.get("trace_id", "")
    status = record.get("final_status") or record.get("response_status")
    fallback_reason = record.get("fallback_reason")
    retrieval_mode = record.get("retrieval_mode")
    domain_hint = record.get("domain_hint")
    retrieved = record.get("retrieved_chunks") or []
    resolution = record.get("audit_resolution", "open")
    return (
        f"[{source}] category={audit_category(record)} resolution={resolution} trace_id={trace_id} "
        f"query={query!r} status={status!r} fallback_reason={fallback_reason!r} "
        f"retrieval_mode={retrieval_mode!r} domain_hint={domain_hint!r} "
        f"retrieved_chunks={retrieved}"
    )


def annotate_resolution(
    record: dict[str, Any],
    traces_by_query: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    resolution = "open"
    query_key = _query_key(record)
    created_at = _created_at(record)
    if query_key and created_at:
        for trace in traces_by_query.get(query_key, []):
            if _created_at(trace) > created_at and _is_success_trace(trace):
                resolution = "closed_by_later_success"
                break
    return {**record, "audit_resolution": resolution}


def _merge_hard_case_with_trace(
    hard_case: dict[str, Any],
    trace_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    trace_id = str(hard_case.get("trace_id", ""))
    trace = trace_by_id.get(trace_id, {})
    return {
        **trace,
        **hard_case,
        "final_status": trace.get("final_status"),
        "retrieval_mode": trace.get("retrieval_mode"),
        "retrieved_chunks": trace.get("retrieved_chunks"),
        "created_at": hard_case.get("created_at") or trace.get("created_at"),
    }


def _group_traces_by_query(records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        key = _query_key(record)
        if not key:
            continue
        grouped.setdefault(key, []).append(record)
    for items in grouped.values():
        items.sort(key=_created_at)
    return grouped


def _query_key(record: dict[str, Any]) -> str:
    query = record.get("normalized_query") or record.get("raw_query") or ""
    return str(query).strip()


def _created_at(record: dict[str, Any]) -> str:
    return str(record.get("created_at") or "")


def _is_success_trace(record: dict[str, Any]) -> bool:
    return record.get("final_status") == "ok" and not is_bad_trace(record)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit provider bad cases from retrieval traces and hard cases"
    )
    parser.add_argument(
        "--provider",
        default=",".join(DEFAULT_PROVIDER_NAMES),
        help="comma-separated planner provider names to inspect",
    )
    parser.add_argument(
        "--router-used",
        default="",
        help="comma-separated router_used values; overrides --provider when set",
    )
    parser.add_argument(
        "--include-local",
        action="store_true",
        help="also include query_planner_local in the audit",
    )
    parser.add_argument(
        "--repo-root",
        default=str(repo_root()),
        help="repository root containing backend/app/storage",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="max number of records to print per section",
    )
    args = parser.parse_args()

    provider_names = parse_csv(args.provider)
    router_names = (
        parse_csv(args.router_used)
        if args.router_used.strip()
        else router_names_for_providers(provider_names, include_local=args.include_local)
    )
    report = build_audit_report(root=Path(args.repo_root), router_names=router_names)
    print(render_audit_report(report, limit=args.limit))


if __name__ == "__main__":
    main()
