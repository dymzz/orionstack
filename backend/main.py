from contextlib import asynccontextmanager

from elasticsearch import Elasticsearch
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.auth import router as auth_router
from app.api.routes.chat import router as chat_router
from app.api.routes.documents import router as documents_router
from app.api.routes.extraction import router as extraction_router
from app.api.routes.health import router as health_router
from app.config.settings import settings
from app.indexing.elastic_indexer import ElasticIndexer
from app.storage.repositories.chunk_repo import ChunkRepository
from app.storage.repositories.faq_repo import FAQRepository
from app.storage.repositories.knowledge_unit_repo import KnowledgeUnitRepository


@asynccontextmanager
async def lifespan(app: FastAPI):
    es = None
    app.state.elastic_indexed_count = 0
    app.state.elastic_indexing_error = None

    try:
        if settings.search_backend == "elasticsearch":
            es = Elasticsearch(
                settings.elastic_url,
                request_timeout=2,
                max_retries=0,
                retry_on_timeout=False,
            )

            indexer = ElasticIndexer(es, index_name=settings.elastic_index)
            ku_repo = KnowledgeUnitRepository(
                faq_repo=FAQRepository(),
                chunk_repo=ChunkRepository(),
            )
            units = ku_repo.list_all()

            indexer.ensure_index(use_ik_analyzer=settings.elastic_use_ik_analyzer)
            indexed = indexer.index_units(units)
            app.state.elastic_indexed_count = indexed
    except Exception as exc:
        app.state.elastic_indexing_error = str(exc)
        print(f"[orionstack] elastic indexing skipped: {exc}")

    try:
        yield
    finally:
        if es is not None:
            try:
                es.close()
            except Exception:
                pass


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(documents_router)
app.include_router(extraction_router)
