from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

from app.storage.models.cleanup_task import CleanupTask
from app.storage.repositories.cleanup_task_repo import CleanupTaskRepo
from app.storage.repositories.source_record_repo import SourceRecordRepo

_logger = logging.getLogger("orionstack.cleanup")

_CLEANUP_ELIGIBLE_STATUSES = {"revoked", "deleted", "superseded"}


class CleanupBackend(Protocol):
    def delete_by_source_record(self, source_record_id: str) -> dict[str, Any]:
        ...


@dataclass(frozen=True)
class CleanupBackendResult:
    backend: str
    status: str
    detail: dict[str, Any]
    error_summary: str | None = None


@dataclass(frozen=True)
class CleanupTaskResult:
    task: CleanupTask
    source_status: str | None
    elastic: CleanupBackendResult
    vector: CleanupBackendResult


@dataclass(frozen=True)
class CleanupTaskBatchResult:
    processed: int
    completed: int
    failed: int
    skipped: int
    results: list[CleanupTaskResult]


class TombstoneCleanupService:
    def __init__(
        self,
        *,
        cleanup_task_repo: CleanupTaskRepo | None = None,
        source_record_repo: SourceRecordRepo | None = None,
        elastic_indexer: CleanupBackend | None = None,
        vector_cleanup_backend: CleanupBackend | None = None,
    ) -> None:
        self._cleanup_task_repo = cleanup_task_repo or CleanupTaskRepo()
        self._source_record_repo = source_record_repo or SourceRecordRepo()
        self._elastic_indexer = elastic_indexer
        self._vector_cleanup_backend = vector_cleanup_backend

    def run_next(self) -> CleanupTaskResult | None:
        pending_tasks = self._cleanup_task_repo.list_by_status("pending")
        if not pending_tasks:
            return None
        return self.run_task(pending_tasks[0].cleanup_task_id)

    def run_pending(self, *, limit: int = 10) -> CleanupTaskBatchResult:
        if limit <= 0:
            return CleanupTaskBatchResult(
                processed=0,
                completed=0,
                failed=0,
                skipped=0,
                results=[],
            )

        results: list[CleanupTaskResult] = []
        completed = 0
        failed = 0
        skipped = 0

        for _ in range(limit):
            result = self.run_next()
            if result is None:
                break

            results.append(result)
            if result.task.status == "completed":
                completed += 1
            elif result.task.status == "failed":
                failed += 1
            else:
                skipped += 1

        return CleanupTaskBatchResult(
            processed=len(results),
            completed=completed,
            failed=failed,
            skipped=skipped,
            results=results,
        )

    def run_task(self, cleanup_task_id: str) -> CleanupTaskResult | None:
        task = self._cleanup_task_repo.get(cleanup_task_id)
        if task is None:
            return None
        if task.status != "pending":
            return CleanupTaskResult(
                task=task,
                source_status=task.source_status,
                elastic=_skipped_backend("elastic", "task_not_pending"),
                vector=_skipped_backend("vector", "task_not_pending"),
            )

        processing = self._cleanup_task_repo.update_status(
            task.cleanup_task_id,
            "processing",
            started_at=_now(),
        )
        if processing is None:
            _logger.warning("cleanup_task_processing_failed task=%s", cleanup_task_id)
            return None

        _logger.info("cleanup_task_started task=%s source_record=%s", cleanup_task_id, processing.source_record_id)

        source_record = self._source_record_repo.get(processing.source_record_id)
        source_status = (
            source_record.status if source_record is not None else processing.source_status
        )
        if source_status not in _CLEANUP_ELIGIBLE_STATUSES:
            return self._finish(
                processing,
                "skipped",
                source_status=source_status,
                elastic=_skipped_backend("elastic", "source_status_not_cleanup_eligible"),
                vector=_skipped_backend("vector", "source_status_not_cleanup_eligible"),
            )

        elastic = _delete_with_backend(
            "elastic",
            self._elastic_indexer,
            processing.source_record_id,
        )
        # The vector backend is intentionally optional. The current local vector
        # retrieval is computed from ES hits, while future vector stores can plug
        # in here without changing tombstone cleanup orchestration.
        vector = _delete_with_backend(
            "vector",
            self._vector_cleanup_backend,
            processing.source_record_id,
        )

        final_status = _resolve_task_status(elastic, vector)
        _logger.info(
            "cleanup_task_finished task=%s status=%s elastic=%s vector=%s",
            cleanup_task_id,
            final_status,
            elastic.status,
            vector.status,
        )
        return self._finish(
            processing,
            final_status,
            source_status=source_status,
            elastic=elastic,
            vector=vector,
        )

    def _finish(
        self,
        task: CleanupTask,
        status: str,
        *,
        source_status: str | None,
        elastic: CleanupBackendResult,
        vector: CleanupBackendResult,
    ) -> CleanupTaskResult:
        finished = self._cleanup_task_repo.update_status(
            task.cleanup_task_id,
            status,
            finished_at=_now(),
            error_summary=_build_error_summary(
                source_status=source_status,
                elastic=elastic,
                vector=vector,
            ),
        )
        return CleanupTaskResult(
            task=finished or task,
            source_status=source_status,
            elastic=elastic,
            vector=vector,
        )


def _delete_with_backend(
    backend_name: str,
    backend: CleanupBackend | None,
    source_record_id: str,
) -> CleanupBackendResult:
    if backend is None:
        return _skipped_backend(
            backend_name,
            f"{backend_name}_cleanup_backend_not_configured",
        )

    try:
        detail = backend.delete_by_source_record(source_record_id)
    except Exception as error:
        return CleanupBackendResult(
            backend=backend_name,
            status="failed",
            detail={},
            error_summary=f"{error.__class__.__name__}: {error}",
        )

    return CleanupBackendResult(
        backend=backend_name,
        status="completed",
        detail=detail,
    )


def _resolve_task_status(
    elastic: CleanupBackendResult,
    vector: CleanupBackendResult,
) -> str:
    statuses = {elastic.status, vector.status}
    if "failed" in statuses:
        return "failed"
    if statuses == {"skipped"}:
        return "skipped"
    return "completed"


def _skipped_backend(backend_name: str, reason: str) -> CleanupBackendResult:
    return CleanupBackendResult(
        backend=backend_name,
        status="skipped",
        detail={"reason": reason},
    )


def _build_error_summary(
    *,
    source_status: str | None,
    elastic: CleanupBackendResult,
    vector: CleanupBackendResult,
) -> str:
    return json.dumps(
        {
            "source_status": source_status,
            "elastic": _backend_to_summary(elastic),
            "vector": _backend_to_summary(vector),
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def _backend_to_summary(result: CleanupBackendResult) -> dict[str, Any]:
    return {
        "backend": result.backend,
        "status": result.status,
        "detail": result.detail,
        "error_summary": result.error_summary,
    }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
