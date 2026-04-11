from fastapi import FastAPI

from app.api.routes.sessions import router as sessions_router
from app.api.routes.documents import router as documents_router
from app.api.routes.qa import router as qa_router
from app.api.routes.feedback import router as feedback_router
from app.api.routes.audit import router as audit_router


def create_app() -> FastAPI:
    app = FastAPI(title="OrionStack API", version="0.1.0")

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
