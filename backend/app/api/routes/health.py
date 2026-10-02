from typing import Any

from fastapi import APIRouter, Depends, Request, Response, status

from app.api.auth import require_admin
from app.config.settings import settings

router = APIRouter()


@router.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz")
def readyz(request: Request, response: Response) -> dict[str, Any]:
    config_errors = settings.production_config_errors()
    elasticsearch = _build_elasticsearch_status(request)
    errors = [*config_errors, *elasticsearch["errors"]]
    ready = not errors

    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "ready" if ready else "not_ready",
    }


@router.get("/readyz/detail", dependencies=[Depends(require_admin)])
def readyz_detail(request: Request) -> dict[str, Any]:
    config_errors = settings.production_config_errors()
    elasticsearch = _build_elasticsearch_status(request)

    return {
        "status": "ready" if not (config_errors or elasticsearch["errors"]) else "not_ready",
        "app_name": settings.app_name,
        "app_version": request.app.version,
        "app_mode": settings.app_mode,
        "search_backend": settings.search_backend,
        "config": {
            "production_safe": not config_errors,
            "errors": config_errors,
        },
        "elasticsearch": elasticsearch,
    }


def _build_elasticsearch_status(request: Request) -> dict[str, Any]:
    if settings.search_backend != "elasticsearch":
        return {
            "enabled": False,
            "index_name": None,
            "indexed_count": None,
            "indexing_error": None,
            "errors": [],
        }

    indexing_error = getattr(request.app.state, "elastic_indexing_error", None)
    indexed_count = getattr(request.app.state, "elastic_indexed_count", 0)
    errors = [indexing_error] if indexing_error else []
    return {
        "enabled": True,
        "index_name": settings.elastic_index,
        "indexed_count": indexed_count,
        "indexing_error": indexing_error,
        "errors": errors,
    }
