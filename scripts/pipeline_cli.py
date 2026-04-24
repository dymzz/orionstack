"""Extract knowledge candidates from a document file via Qwen API.

Usage:
    # Step 1: Import document into SourceRecord
    python -m scripts.pipeline_import --file path/to/document.md --title "title" --source-system wiki

    # Step 2: Extract candidates from a SourceRecord
    python -m scripts.pipeline_extract --source-record-id sr-xxx [--candidate-types faq] [--auto-approve]

    # Step 3 (if not --auto-approve): Review candidates one by one
    python -m scripts.pipeline_review --candidate-id ec-xxx --approve
    python -m scripts.pipeline_review --candidate-id ec-xxx --reject

    # Full pipeline in one command (import + extract + auto-approve + publish)
    python -m scripts.pipeline_import --file path/to/document.md --title "title" --source-system wiki --auto-approve
"""
from __future__ import annotations

import argparse
import json
import sys
import socket
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
socket.setdefaulttimeout(60)


def cmd_import(args: argparse.Namespace) -> None:
    from app.storage.models.source_record import SourceRecord
    from app.storage.repositories.source_record_repo import SourceRecordRepo

    file_path = Path(args.file)
    if not file_path.exists():
        print(f"[error] file not found: {file_path}")
        sys.exit(1)

    content = file_path.read_text(encoding="utf-8")
    title = args.title or file_path.stem
    source_system = args.source_system or "manual_upload"
    now = datetime.now(timezone.utc).isoformat()
    sr_id = args.source_record_id or f"sr-{source_system}-{SourceRecord.compute_content_hash(content)}"

    record = SourceRecord(
        source_record_id=sr_id,
        tenant_id="default",
        source_system=source_system,
        source_object_type=args.object_type or "policy_doc",
        external_id=sr_id,
        source_locator=f"file://{file_path}",
        title=title,
        raw_content=content,
        content_hash=SourceRecord.compute_content_hash(content),
        source_updated_at=now,
        export_batch_id="batch-pipeline-import",
        access_scope=args.access_scope or "internal",
        status="active",
        synced_at=now,
    )

    repo = SourceRecordRepo()
    repo.upsert(record)
    print(f"[import] {record.source_record_id}")
    print(f"  title: {title}")
    print(f"  source_system: {source_system}")
    print(f"  content: {len(content)} chars")

    if args.auto_approve:
        args.source_record_id = record.source_record_id
        _extract_and_publish(args)


def cmd_extract(args: argparse.Namespace) -> None:
    _extract_and_publish(args)


def _extract_and_publish(args: argparse.Namespace) -> None:
    from app.storage.repositories.source_record_repo import SourceRecordRepo
    from app.extract.extraction_service import ExtractionService

    repo = SourceRecordRepo()
    sr = repo.get(args.source_record_id)
    if sr is None:
        print(f"[error] source_record not found: {args.source_record_id}")
        sys.exit(1)

    print(f"[extract] calling Qwen API on: {sr.title}")
    candidate_types = args.candidate_types.split(",") if args.candidate_types else None
    service = ExtractionService()
    candidates = service.extract_from_record(sr, candidate_types=candidate_types)

    print(f"[extract] got {len(candidates)} candidates")
    for c in candidates:
        payload = json.loads(c.payload_json)
        ct = payload.get("candidate_type", c.candidate_type)
        label = payload.get("question") or payload.get("label") or payload.get("query_key") or ""
        print(f"  [{c.candidate_id}] {ct}: {label[:60]}")

    if args.auto_approve:
        _batch_approve_and_publish(candidates, sr)


def cmd_review(args: argparse.Namespace) -> None:
    from app.storage.repositories.extraction_candidate_repo import ExtractionCandidateRepo
    from app.storage.repositories.source_record_repo import SourceRecordRepo
    from app.extract.candidate_reviewer import review_candidate, publish_candidate

    ec_repo = ExtractionCandidateRepo()
    sr_repo = SourceRecordRepo()
    approved = args.approve and not args.reject

    reviewed = review_candidate(
        args.candidate_id,
        approved=approved,
        reviewer=args.reviewer or "cli",
        candidate_repo=ec_repo,
    )
    if reviewed is None:
        print(f"[error] candidate not found: {args.candidate_id}")
        sys.exit(1)

    print(f"[review] {reviewed.candidate_id} -> {reviewed.review_status}")

    if approved:
        sr = sr_repo.get(reviewed.source_record_id)
        if sr:
            result = publish_candidate(reviewed, sr)
            if result:
                print(f"[publish] -> {type(result).__name__}")


def cmd_list(args: argparse.Namespace) -> None:
    from app.storage.repositories.extraction_candidate_repo import ExtractionCandidateRepo

    repo = ExtractionCandidateRepo()
    status = args.status or "pending"
    candidates = repo.list_by_review_status(status)
    print(f"[list] {len(candidates)} candidates with status={status}")
    for c in candidates:
        payload = json.loads(c.payload_json)
        ct = payload.get("candidate_type", c.candidate_type)
        label = payload.get("question") or payload.get("label") or payload.get("query_key") or ""
        print(f"  [{c.candidate_id}] {ct}: {label[:60]}")


def _batch_approve_and_publish(candidates, sr) -> None:
    from app.storage.repositories.extraction_candidate_repo import ExtractionCandidateRepo
    from app.extract.candidate_reviewer import review_candidate, publish_candidate

    ec_repo = ExtractionCandidateRepo()
    published_types: list[str] = []

    for c in candidates:
        reviewed = review_candidate(c.candidate_id, True, reviewer="pipeline_auto", candidate_repo=ec_repo)
        if reviewed is None:
            continue
        result = publish_candidate(reviewed, sr)
        if result:
            published_types.append(type(result).__name__)

    print(f"[publish] auto-approved and published {len(published_types)} items: {published_types}")


def main() -> None:
    parser = argparse.ArgumentParser(description="OrionStack extraction pipeline CLI")
    sub = parser.add_subparsers(dest="command")

    # import
    p_import = sub.add_parser("import", help="Import a document file into SourceRecord")
    p_import.add_argument("--file", required=True, help="Path to document file (.txt, .md)")
    p_import.add_argument("--title", help="Document title (default: filename)")
    p_import.add_argument("--source-system", default="manual_upload", help="Source system identifier")
    p_import.add_argument("--object-type", default="policy_doc", help="Source object type")
    p_import.add_argument("--access-scope", default="internal", help="Access scope")
    p_import.add_argument("--source-record-id", help="Override source record ID")
    p_import.add_argument("--auto-approve", action="store_true", help="Extract + auto-approve + publish after import")
    p_import.add_argument("--candidate-types", help="Comma-separated types: faq,action_link,dynamic_query (only used with --auto-approve)")

    # extract
    p_extract = sub.add_parser("extract", help="Extract candidates from a SourceRecord via Qwen API")
    p_extract.add_argument("--source-record-id", required=True, help="SourceRecord ID to extract from")
    p_extract.add_argument("--candidate-types", help="Comma-separated types: faq,action_link,dynamic_query")
    p_extract.add_argument("--auto-approve", action="store_true", help="Auto-approve and publish all extracted candidates")

    # review
    p_review = sub.add_parser("review", help="Approve or reject a candidate")
    p_review.add_argument("--candidate-id", required=True, help="ExtractionCandidate ID")
    p_review.add_argument("--approve", action="store_true", help="Approve the candidate")
    p_review.add_argument("--reject", action="store_true", help="Reject the candidate")
    p_review.add_argument("--reviewer", default="cli", help="Reviewer name")

    # list
    p_list = sub.add_parser("list", help="List candidates by status")
    p_list.add_argument("--status", default="pending", help="Review status filter (pending/approved/rejected)")

    args = parser.parse_args()

    if args.command == "import":
        cmd_import(args)
    elif args.command == "extract":
        cmd_extract(args)
    elif args.command == "review":
        cmd_review(args)
    elif args.command == "list":
        cmd_list(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
