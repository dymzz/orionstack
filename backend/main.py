from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes.sessions import router as sessions_router
from app.api.routes.documents import router as documents_router
from app.api.routes.qa import router as qa_router
from app.api.routes.feedback import router as feedback_router
from app.api.routes.audit import router as audit_router
from app.knowledge.indexing.index_dispatcher import index_dispatcher


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        yield
    finally:
        index_dispatcher.shutdown()


def create_app() -> FastAPI:
    app = FastAPI(title="OrionStack API", version="0.1.0", lifespan=lifespan)

    app.include_router(sessions_router, prefix="/api/v1")
    app.include_router(documents_router, prefix="/api/v1")
    app.include_router(qa_router, prefix="/api/v1")
    app.include_router(feedback_router, prefix="/api/v1")
    app.include_router(audit_router, prefix="/api/v1")

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
