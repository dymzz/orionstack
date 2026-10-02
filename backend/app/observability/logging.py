from __future__ import annotations

import contextvars
import json
import logging
import sys
import time
from typing import Any

from fastapi import Request, Response

from app.config.settings import settings

trace_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("trace_id", default="")


class StructuredFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        event: dict[str, Any] = {
            "ts": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        tid = trace_id_ctx.get("")
        if tid:
            event["trace_id"] = tid
        if record.exc_info and record.exc_info[0] is not None:
            event["exc"] = self.formatException(record.exc_info)
        return json.dumps(event, ensure_ascii=False)


def configure_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(StructuredFormatter(datefmt="%Y-%m-%dT%H:%M:%S"))
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, settings.log_level, logging.INFO))


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


async def log_request(request: Request, call_next) -> Response:
    if not settings.access_log_enabled:
        return await call_next(request)

    logger = get_logger("orionstack.request")
    started_at = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        duration_ms = int((time.perf_counter() - started_at) * 1000)
        logger.exception(
            "request_failed method=%s path=%s duration_ms=%s",
            request.method,
            request.url.path,
            duration_ms,
        )
        raise

    duration_ms = int((time.perf_counter() - started_at) * 1000)
    logger.info(
        "request_completed method=%s path=%s status_code=%s duration_ms=%s",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response