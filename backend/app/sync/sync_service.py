from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, TypeAlias
from uuid import uuid4

from app.sync.sync_parser import parse_export_file
from app.storage.models.import_batch import ImportBatch
from app.storage.models.source_record import SourceRecord
from app.storage.repositories.source_record_repo import SourceRecordRepo
from app.storage.repositories.import_batch_repo import ImportBatchRepo
from app.storage.repositories.knowledge_unit_repo import KnowledgeUnitRepository
from app.storage.repositories.extraction_task_repo import ExtractionTaskRepo


_SUPERSEDED_KNOWLEDGE_UNIT_STATUS = "deprecated"
_NEW_SOURCE_EXTRACTION_REASON = "new_source_record"
_UPDATED_SOURCE_EXTRACTION_REASON = "source_record_updated"
_SyncResult: TypeAlias = Literal["added", "updated", "unchanged"]


class SyncService:
    def __init__(
        self,
        source_record_repo: SourceRecordRepo,
        import_batch_repo: ImportBatchRepo,
        *,
        knowledge_unit_repo: KnowledgeUnitRepository | None = None,
        extraction_task_repo: ExtractionTaskRepo | None = None,
        elastic_indexer=None,
    ) -> None:
        self._sr_repo = source_record_repo
        self._ib_repo = import_batch_repo
        self._ku_repo = knowledge_unit_repo
        self._extraction_task_repo = extraction_task_repo
        self._elastic_indexer = elastic_indexer

    def sync_file(
        self,
        path: Path,
        source_system: str,
        mode: str = "incremental",
        tenant_id: str = "default",
    ) -> ImportBatch:
        batch_id = f"ib-{uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        batch = ImportBatch(
            import_batch_id=batch_id,
            tenant_id=tenant_id,
            source_system=source_system,
            mode=mode,
            started_at=now,
            status="running",
        )
        self._ib_repo.create(batch)

        try:
            records = parse_export_file(path, source_system, batch_id, tenant_id)
        except Exception as error:
            return self._finish_batch(
                batch,
                record_count=0,
                added=0,
                updated=0,
                unchanged=0,
                failed=1,
                errors=[_format_batch_error("parse", error)],
            )

        added = 0
        updated = 0
        unchanged = 0
        failed = 0
        errors: list[str] = []

        for index, record in enumerate(records, start=1):
            try:
                result = self._sync_record(record, batch_id)
            except Exception as error:
                failed += 1
                errors.append(_format_record_error(index, record.external_id, error))
                continue

            if result == "added":
                added += 1
            elif result == "updated":
                updated += 1
            else:
                unchanged += 1

        return self._finish_batch(
            batch,
            record_count=len(records),
            added=added,
            updated=updated,
            unchanged=unchanged,
            failed=failed,
            errors=errors,
        )

    def _sync_record(self, record: SourceRecord, batch_id: str) -> _SyncResult:
        existing = self._sr_repo._find_active_by_system_and_external(
            record.source_system, record.external_id
        )
        record = replace(record, import_batch_id=batch_id)

        if existing is None:
            self._sr_repo.upsert(record)
            self._enqueue_extraction_task(record, reason=_NEW_SOURCE_EXTRACTION_REASON)
            return "added"

        if existing.content_hash == record.content_hash:
            return "unchanged"

        self._deprecate_published_units(existing.source_record_id)
        self._sr_repo.update_status(existing.source_record_id, "superseded")
        self._sr_repo.upsert(record)
        self._enqueue_extraction_task(
            record,
            reason=_UPDATED_SOURCE_EXTRACTION_REASON,
            supersedes_source_record_id=existing.source_record_id,
        )
        return "updated"

    def _finish_batch(
        self,
        batch: ImportBatch,
        *,
        record_count: int,
        added: int,
        updated: int,
        unchanged: int,
        failed: int,
        errors: list[str],
    ) -> ImportBatch:
        finished = datetime.now(timezone.utc).isoformat()
        batch = replace(
            batch,
            status=_resolve_batch_status(record_count, failed),
            finished_at=finished,
            record_count=record_count,
            error_summary=_build_error_summary(
                added=added,
                updated=updated,
                unchanged=unchanged,
                failed=failed,
                errors=errors,
            ),
        )
        self._ib_repo.update(batch)
        return batch

    def _deprecate_published_units(self, source_record_id: str) -> None:
        if self._ku_repo is not None:
            self._ku_repo.update_status_by_source_record(
                source_record_id,
                _SUPERSEDED_KNOWLEDGE_UNIT_STATUS,
            )

        if self._elastic_indexer is not None:
            self._elastic_indexer.update_status_by_source_record(
                source_record_id,
                _SUPERSEDED_KNOWLEDGE_UNIT_STATUS,
            )

    def _enqueue_extraction_task(
        self,
        record: SourceRecord,
        *,
        reason: str,
        supersedes_source_record_id: str | None = None,
    ) -> None:
        if self._extraction_task_repo is None:
            return

        self._extraction_task_repo.enqueue_for_source_record(
            record,
            reason=reason,
            supersedes_source_record_id=supersedes_source_record_id,
        )


def _resolve_batch_status(record_count: int, failed: int) -> str:
    if failed == 0:
        return "success"
    if record_count > failed:
        return "partial_success"
    return "failed"


def _build_error_summary(
    *,
    added: int,
    updated: int,
    unchanged: int,
    failed: int,
    errors: list[str],
) -> str:
    return json.dumps(
        {
            "added": added,
            "updated": updated,
            "unchanged": unchanged,
            "failed": failed,
            "errors": errors,
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def _format_batch_error(stage: str, error: Exception) -> str:
    return f"{stage}: {error.__class__.__name__}: {error}"


def _format_record_error(index: int, external_id: str, error: Exception) -> str:
    return (
        f"record[{index}] external_id={external_id}: "
        f"{error.__class__.__name__}: {error}"
    )
