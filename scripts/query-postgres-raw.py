"""Embedding -> pgvector -> immutable raw facts, with explicitly selected processing."""

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.config.core_settings import CoreConfigurationError
from app.knowledge.contracts import AccessContext, QueryContext
from app.knowledge.postgres import DatabaseUnavailable
from app.providers.http import ProviderError
from app.retrieval.raw_pipeline import RawRetrievalPipeline


def main() -> int:
    parser = argparse.ArgumentParser(description="Run and record raw vector retrieval; Jev is optional")
    parser.add_argument("--query", required=True)
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--scope", action="append", default=None)
    parser.add_argument("--document-id", action="append", default=None)
    parser.add_argument("--top-k", type=int, default=20)
    parser.add_argument("--final-top-k", type=int, default=None)
    parser.add_argument("--with-jev", action="store_true")
    args = parser.parse_args()
    try:
        processors = ()
        if args.with_jev:
            from app.decision.retrieval_processors import JevRetrievalProcessor
            processors = (JevRetrievalProcessor(),)
        response = RawRetrievalPipeline(processors=processors).retrieve(
            QueryContext(query=args.query, document_ids=tuple(args.document_id or ())),
            AccessContext(tenant_id=args.tenant_id, user_id=args.user_id,
                          allowed_scopes=tuple(args.scope or ("internal",))),
            top_k=args.top_k, final_top_k=args.final_top_k,
        )
        print(json.dumps({
            "event_id": response.raw.event.id, "processing_run_id": response.processing.id,
            "status": response.processing.status, "error_code": response.processing.error_code,
            "raw_candidate_count": len(response.raw.candidates),
            "final_candidates": [{"candidate_id": candidate.candidate_id, "document_id": candidate.document_id,
                                  "chunk_id": candidate.chunk_id, "document_version": candidate.document_version,
                                  "raw_rank": candidate.rank, "raw_similarity_score": candidate.similarity_score,
                                  "final_rank": rank}
                                 for rank, candidate in enumerate(response.final_candidates, 1)],
        }, ensure_ascii=False, indent=2))
        return 0
    except (CoreConfigurationError, DatabaseUnavailable, ProviderError, ValueError, PermissionError) as error:
        print(f"[orionstack] {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
