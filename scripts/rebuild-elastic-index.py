from __future__ import annotations

import sys
from pathlib import Path

from elasticsearch import Elasticsearch

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config.settings import settings
from app.indexing.elastic_indexer import ElasticIndexer
from app.storage.repositories.chunk_repo import ChunkRepository
from app.storage.repositories.faq_repo import FAQRepository
from app.storage.repositories.knowledge_unit_repo import KnowledgeUnitRepository


def main() -> int:
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


if __name__ == "__main__":
    raise SystemExit(main())
