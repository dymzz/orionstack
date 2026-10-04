"""Preview authorized pending chunks; --apply embeds one bounded batch with the selected provider."""

import argparse
from dataclasses import replace
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.config.core_settings import CoreConfigurationError, CoreSettings
from app.knowledge.contracts import AccessContext
from app.knowledge.embedding import create_embedding_client
from app.knowledge.postgres import DatabaseUnavailable, PostgresDatabase
from app.providers.http import ProviderError
from app.retrieval.postgres_vector import EmbeddingWriteConflict, PostgresEmbeddingRepository


def main() -> int:
    parser = argparse.ArgumentParser(description="Preview or embed one authorized PostgreSQL chunk batch")
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--scope", action="append", default=None)
    parser.add_argument("--limit", type=int, default=32)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--embedding-provider", choices=("onnx", "cloudflare_workers_ai"))
    args = parser.parse_args()
    try:
        settings = CoreSettings()
        if args.embedding_provider:
            settings = replace(settings, embedding_provider=args.embedding_provider)
        access = AccessContext(tenant_id=args.tenant_id, user_id="embedding-maintenance", roles=("admin",),
                               allowed_scopes=tuple(args.scope or ("internal",)))
        client = create_embedding_client(settings)
        repository = PostgresEmbeddingRepository(PostgresDatabase(settings))
        chunks = repository.pending_chunks(access, client.signature, args.limit)
        report = {"mode": "preview", "pending_in_batch": len(chunks),
                  "model": client.signature.model, "embedding_signature": client.signature.fingerprint}
        if args.apply and chunks:
            batch = client.embed(tuple(chunk["body_text"] for chunk in chunks))
            report["written"] = repository.save_batch(access, chunks, batch)
            report["mode"] = "applied"
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except (CoreConfigurationError, DatabaseUnavailable, ProviderError, EmbeddingWriteConflict, ValueError) as error:
        print(f"[orionstack] {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
