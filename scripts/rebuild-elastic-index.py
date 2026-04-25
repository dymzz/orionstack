from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"


def _configure_backend_imports() -> None:
    if str(BACKEND_DIR) not in sys.path:
        sys.path.insert(0, str(BACKEND_DIR))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Rebuild the Elasticsearch index from local KnowledgeUnit data."
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Print the resolved index configuration and exit without touching Elasticsearch.",
    )
    return parser


def _load_settings():
    _configure_backend_imports()
    from app.config.settings import settings

    return settings


def _run_reindex(settings) -> int:
    from elasticsearch import Elasticsearch

    from app.indexing.elastic_indexer import ElasticIndexer
    from app.storage.repositories.chunk_repo import ChunkRepository
    from app.storage.repositories.faq_repo import FAQRepository
    from app.storage.repositories.knowledge_unit_repo import KnowledgeUnitRepository

    print(f"[reindex] elastic_url={settings.elastic_url}")
    print(f"[reindex] elastic_index={settings.elastic_index}")

    es = Elasticsearch(
        settings.elastic_url,
        request_timeout=10,
        max_retries=0,
        retry_on_timeout=False,
    )

    try:
        indexer = ElasticIndexer(es, index_name=settings.elastic_index)
        ku_repo = KnowledgeUnitRepository(
            faq_repo=FAQRepository(),
            chunk_repo=ChunkRepository(),
        )

        units = ku_repo.list_all()
        print(f"[reindex] collected knowledge units: {len(units)}")

        indexer.ensure_index()
        indexed = indexer.index_units(units)

        print(f"[reindex] indexed documents: {indexed}")
        return 0
    finally:
        es.close()


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    settings = _load_settings()

    if args.check_only:
        print(f"[reindex] elastic_url={settings.elastic_url}")
        print(f"[reindex] elastic_index={settings.elastic_index}")
        print("[reindex] check only passed; no Elasticsearch write performed.")
        return 0

    return _run_reindex(settings)


if __name__ == "__main__":
    raise SystemExit(main())
