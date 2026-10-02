from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.storage.models.extraction_task import ExtractionTask
from app.storage.models.source_record import SourceRecord
from app.storage.repositories.base_repo import JsonlLock

_STORAGE_DIR = Path(__file__).resolve().parents[1] / "extraction_tasks"


class ExtractionTaskRepo:
    def __init__(self, storage_dir: Path | None = None) -> None:
        self._dir = storage_dir or _STORAGE_DIR
        self._dir.mkdir(parents=True, exist_ok=True)
        self._file = self._dir / "tasks.jsonl"
        self._lock = JsonlLock(self._file)

    def create(self, task: ExtractionTask) -> None:
        with self._lock:
            self._append(task)

    def enqueue_for_source_record(
        self,
        record: SourceRecord,
        *,
        reason: str,
        supersedes_source_record_id: str | None = None,
    ) -> ExtractionTask:
        task = ExtractionTask(
            extraction_task_id=f"et-{uuid4().hex[:12]}",
            tenant_id=record.tenant_id,
            source_record_id=record.source_record_id,
            source_system=record.source_system,
            external_id=record.external_id,
            reason=reason,
            status="pending",
            import_batch_id=record.import_batch_id,
            supersedes_source_record_id=supersedes_source_record_id,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self.create(task)
        return task

    def get(self, extraction_task_id: str) -> ExtractionTask | None:
        for task in self._iter_all():
            if task.extraction_task_id == extraction_task_id:
                return task
        return None

    def list_by_status(self, status: str) -> list[ExtractionTask]:
        return [task for task in self._iter_all() if task.status == status]

    def list_by_source_record(self, source_record_id: str) -> list[ExtractionTask]:
        return [
            task
            for task in self._iter_all()
            if task.source_record_id == source_record_id
        ]

    def update_status(
        self,
        extraction_task_id: str,
        status: str,
        *,
        started_at: str | None = None,
        finished_at: str | None = None,
        error_summary: str | None = None,
    ) -> ExtractionTask | None:
        with self._lock:
            tasks = list(self._iter_all())
            updated: ExtractionTask | None = None
            self._file.write_text("", encoding="utf-8")
            for task in tasks:
                if task.extraction_task_id == extraction_task_id:
                    task = replace(
                        task,
                        status=status,
                        started_at=started_at if started_at is not None else task.started_at,
                        finished_at=(
                            finished_at if finished_at is not None else task.finished_at
                        ),
                        error_summary=error_summary,
                    )
                    updated = task
                self._append(task)
        return updated

    def _append(self, task: ExtractionTask) -> None:
        with open(self._file, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(task.to_dict(), ensure_ascii=False) + "\n")

    def _iter_all(self) -> list[ExtractionTask]:
        if not self._file.exists():
            return []
        results: list[ExtractionTask] = []
        for line in self._file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                results.append(self._parse(json.loads(line)))
        return results

    @staticmethod
    def _parse(d: dict[str, Any]) -> ExtractionTask:
        return ExtractionTask(
            extraction_task_id=d["extraction_task_id"],
            tenant_id=d.get("tenant_id", "default"),
            source_record_id=d["source_record_id"],
            source_system=d.get("source_system", ""),
            external_id=d.get("external_id", ""),
            reason=d.get("reason", ""),
            status=d.get("status", "pending"),
            created_at=d["created_at"],
            import_batch_id=d.get("import_batch_id"),
            supersedes_source_record_id=d.get("supersedes_source_record_id"),
            started_at=d.get("started_at"),
            finished_at=d.get("finished_at"),
            error_summary=d.get("error_summary"),
        )
