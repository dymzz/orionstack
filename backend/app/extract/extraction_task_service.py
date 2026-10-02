from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from app.extract.extraction_service import ExtractionService
from app.storage.models.extraction_candidate import ExtractionCandidate
from app.storage.models.extraction_task import ExtractionTask
from app.storage.repositories.extraction_task_repo import ExtractionTaskRepo

_logger = logging.getLogger("orionstack.extraction_task")
from app.storage.repositories.source_record_repo import SourceRecordRepo


@dataclass(frozen=True)
class ExtractionTaskResult:
    task: ExtractionTask
    candidates: list[ExtractionCandidate]


@dataclass(frozen=True)
class ExtractionTaskBatchResult:
    processed: int
    completed: int
    failed: int
    skipped: int
    results: list[ExtractionTaskResult]


class ExtractionTaskService:
    def __init__(
        self,
        *,
        task_repo: ExtractionTaskRepo | None = None,
        source_record_repo: SourceRecordRepo | None = None,
        extraction_service: ExtractionService | None = None,
    ) -> None:
        self._task_repo = task_repo or ExtractionTaskRepo()
        self._source_record_repo = source_record_repo or SourceRecordRepo()
        self._extraction_service = extraction_service or ExtractionService()

    def run_next(
        self, *, candidate_types: list[str] | None = None
    ) -> ExtractionTaskResult | None:
        pending_tasks = self._task_repo.list_by_status("pending")
        if not pending_tasks:
            return None
        return self.run_task(
            pending_tasks[0].extraction_task_id,
            candidate_types=candidate_types,
        )

    def run_pending(
        self,
        *,
        limit: int = 10,
        candidate_types: list[str] | None = None,
    ) -> ExtractionTaskBatchResult:
        if limit <= 0:
            return ExtractionTaskBatchResult(
                processed=0,
                completed=0,
                failed=0,
                skipped=0,
                results=[],
            )

        results: list[ExtractionTaskResult] = []
        completed = 0
        failed = 0
        skipped = 0

        for _ in range(limit):
            result = self.run_next(candidate_types=candidate_types)
            if result is None:
                break

            results.append(result)
            if result.task.status == "completed":
                completed += 1
            elif result.task.status == "failed":
                failed += 1
            else:
                skipped += 1

        return ExtractionTaskBatchResult(
            processed=len(results),
            completed=completed,
            failed=failed,
            skipped=skipped,
            results=results,
        )

    def run_task(
        self,
        extraction_task_id: str,
        *,
        candidate_types: list[str] | None = None,
    ) -> ExtractionTaskResult | None:
        task = self._task_repo.get(extraction_task_id)
        if task is None:
            return None
        if task.status != "pending":
            return ExtractionTaskResult(task=task, candidates=[])

        started_at = _now()
        processing = self._task_repo.update_status(
            task.extraction_task_id,
            "processing",
            started_at=started_at,
        )
        if processing is None:
            _logger.warning("extraction_task_processing_failed task=%s", extraction_task_id)
            return None

        _logger.info("extraction_task_started task=%s source_record=%s", extraction_task_id, processing.source_record_id)

        source_record = self._source_record_repo.get(processing.source_record_id)
        if source_record is None:
            failed = self._fail_task(
                processing,
                f"source_record_not_found: {processing.source_record_id}",
            )
            return ExtractionTaskResult(task=failed, candidates=[])

        try:
            candidates = self._extraction_service.extract_from_record(
                source_record,
                candidate_types=candidate_types,
            )
        except Exception as error:
            _logger.error("extraction_task_failed task=%s error=%s", extraction_task_id, error)
            failed = self._fail_task(
                processing,
                f"{error.__class__.__name__}: {error}",
            )
            return ExtractionTaskResult(task=failed, candidates=[])

        completed = self._task_repo.update_status(
            processing.extraction_task_id,
            "completed",
            finished_at=_now(),
            error_summary=_build_success_summary(len(candidates)),
        )
        if completed is None:
            return None
        _logger.info(
            "extraction_task_completed task=%s candidates=%d",
            extraction_task_id,
            len(candidates),
        )
        return ExtractionTaskResult(task=completed, candidates=candidates)

    def _fail_task(self, task: ExtractionTask, error_summary: str) -> ExtractionTask:
        failed = self._task_repo.update_status(
            task.extraction_task_id,
            "failed",
            finished_at=_now(),
            error_summary=error_summary,
        )
        return failed or task


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _build_success_summary(extracted_count: int) -> str:
    return json.dumps({"extracted_count": extracted_count}, ensure_ascii=False)
