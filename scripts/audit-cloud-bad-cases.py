import argparse
import json
import os
from collections import Counter


DEFAULT_ROUTER_USED = "query_planner_qwen_api"


def _load_jsonl(path: str) -> list[dict]:
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8") as handle:
        return [
            json.loads(line)
            for line in handle
            if line.strip()
        ]


def _repo_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _trace_path(repo_root: str) -> str:
    return os.path.join(
        repo_root,
        "backend",
        "app",
        "storage",
        "retrieval_traces",
        "retrieval_traces.jsonl",
    )


def _hard_case_path(repo_root: str) -> str:
    return os.path.join(
        repo_root,
        "backend",
        "app",
        "storage",
        "hard_cases",
        "hard_cases.jsonl",
    )


def _is_bad_trace(record: dict) -> bool:
    if record.get("final_status") != "ok":
        return True
    if record.get("fallback_reason") in {
        "no_evidence",
        "retrieval_no_hit",
        "lexical_backend_error",
        "vector_backend_error",
        "ConnectionTimeout",
    }:
        return True
    return False


def _format_trace(record: dict, *, source: str) -> str:
    query = record.get("raw_query", "")
    trace_id = record.get("trace_id", "")
    status = record.get("final_status") or record.get("response_status")
    fallback_reason = record.get("fallback_reason")
    retrieval_mode = record.get("retrieval_mode")
    domain_hint = record.get("domain_hint")
    retrieved = record.get("retrieved_chunks") or []
    return (
        f"[{source}] trace_id={trace_id} query={query!r} status={status!r} "
        f"fallback_reason={fallback_reason!r} retrieval_mode={retrieval_mode!r} "
        f"domain_hint={domain_hint!r} retrieved_chunks={retrieved}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit cloud planner bad cases from retrieval traces"
    )
    parser.add_argument(
        "--router-used",
        default=DEFAULT_ROUTER_USED,
        help="only inspect traces from this router_used value",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="max number of candidate traces to print per section",
    )
    args = parser.parse_args()

    repo_root = _repo_root()
    traces = _load_jsonl(_trace_path(repo_root))
    hard_cases = _load_jsonl(_hard_case_path(repo_root))

    trace_by_id = {
        str(record.get("trace_id", "")): record
        for record in traces
    }

    filtered_traces = [
        record for record in traces
        if record.get("router_used") == args.router_used
    ]
    filtered_hard_cases = [
        record for record in hard_cases
        if record.get("router_used") == args.router_used
    ]

    bad_traces = [record for record in filtered_traces if _is_bad_trace(record)]

    print("[orionstack] cloud bad-case audit")
    print(f"[orionstack] router_used={args.router_used}")
    print(f"[orionstack] traces={len(filtered_traces)} hard_cases={len(filtered_hard_cases)}")
    print(
        f"[orionstack] status={dict(Counter(record.get('final_status') for record in filtered_traces))}"
    )
    print(
        f"[orionstack] fallback_reason={dict(Counter(record.get('fallback_reason') for record in filtered_traces if record.get('fallback_reason') is not None))}"
    )
    print(
        f"[orionstack] retrieval_mode={dict(Counter(record.get('retrieval_mode') for record in filtered_traces))}"
    )
    print()

    print(f"[orionstack] candidate bad traces ({len(bad_traces)})")
    for record in bad_traces[: args.limit]:
        print(_format_trace(record, source="trace"))
    if len(bad_traces) > args.limit:
        print(f"[orionstack] ... truncated {len(bad_traces) - args.limit} more")
    print()

    print(f"[orionstack] hard cases on same router ({len(filtered_hard_cases)})")
    for hard_case in filtered_hard_cases[: args.limit]:
        trace_id = str(hard_case.get("trace_id", ""))
        trace = trace_by_id.get(trace_id, {})
        merged = {
            **trace,
            **hard_case,
            "final_status": trace.get("final_status"),
            "retrieval_mode": trace.get("retrieval_mode"),
            "retrieved_chunks": trace.get("retrieved_chunks"),
        }
        print(_format_trace(merged, source="hard_case"))
    if len(filtered_hard_cases) > args.limit:
        print(
            f"[orionstack] ... truncated {len(filtered_hard_cases) - args.limit} more"
        )


if __name__ == "__main__":
    main()
