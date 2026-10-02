from contextlib import asynccontextmanager
from pathlib import Path
import tomllib

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
from app.observability.logging import configure_logging, get_logger, log_request
from app.storage.repositories.chunk_repo import ChunkRepository
from app.storage.repositories.extracted_faq_repo import ExtractedFaqRepo
from app.storage.repositories.faq_repo import FAQRepository
from app.storage.repositories.knowledge_unit_repo import KnowledgeUnitRepository


configure_logging()
logger = get_logger("orionstack.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    es = None
    app.state.elastic_indexed_count = 0
    app.state.elastic_indexing_error = None

    settings.assert_production_safe()
    logger.info(
        "startup_begin app_mode=%s search_backend=%s planner_provider=%s dynamic_query_adapter=%s",
        settings.app_mode,
        settings.search_backend,
        settings.planner_provider,
        settings.dynamic_query_adapter,
    )
    for warning in settings.startup_warnings():
        logger.warning("config_warning %s", warning)

    try:
        if settings.search_backend == "elasticsearch":
            es = Elasticsearch(
                settings.elastic_url,
                request_timeout=2,
                max_retries=0,
                retry_on_timeout=False,
            )
            app.state.es_client = es

            indexer = ElasticIndexer(es, index_name=settings.elastic_index)
            ku_repo = KnowledgeUnitRepository(
                faq_repo=FAQRepository(),
                chunk_repo=ChunkRepository(),
                extracted_faq_repo=ExtractedFaqRepo(),
            )
            units = ku_repo.list_all()

            indexer.ensure_index(use_ik_analyzer=settings.elastic_use_ik_analyzer)
            indexed = indexer.index_units(units)
            app.state.elastic_indexed_count = indexed
            logger.info(
                "elastic_indexing_completed index=%s indexed_count=%s",
                settings.elastic_index,
                indexed,
            )
    except Exception as exc:
        app.state.elastic_indexing_error = str(exc)
        logger.warning("elastic_indexing_skipped error=%s", exc)

    try:
        yield
    finally:
        if es is not None:
            try:
                es.close()
            except Exception:
                pass
        logger.info("shutdown_complete")


app = FastAPI(
    title=settings.app_name,
    version=tomllib.loads(
        (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(encoding="utf-8")
    )["project"]["version"],
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With", "Accept"],
)


@app.middleware("http")
async def access_log_middleware(request, call_next):
    return await log_request(request, call_next)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(documents_router)
app.include_router(extraction_router)
