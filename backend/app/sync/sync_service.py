from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.sync.sync_parser import parse_export_file
from app.storage.models.import_batch import ImportBatch
from app.storage.repositories.source_record_repo import SourceRecordRepo
from app.storage.repositories.import_batch_repo import ImportBatchRepo
from app.storage.repositories.knowledge_unit_repo import KnowledgeUnitRepository


_SUPERSEDED_KNOWLEDGE_UNIT_STATUS = "deprecated"


class SyncService:
    def __init__(
        self,
        source_record_repo: SourceRecordRepo,
        import_batch_repo: ImportBatchRepo,
        *,
        knowledge_unit_repo: KnowledgeUnitRepository | None = None,
        elastic_indexer=None,
    ) -> None:
        self._sr_repo = source_record_repo
        self._ib_repo = import_batch_repo
        self._ku_repo = knowledge_unit_repo
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

        records = parse_export_file(path, source_system, batch_id, tenant_id)
        added = 0
        updated = 0
        unchanged = 0

        for record in records:
            existing = self._sr_repo._find_active_by_system_and_external(
                record.source_system, record.external_id
            )
            if existing is None:
                from dataclasses import replace
                record = replace(record, import_batch_id=batch_id)
                self._sr_repo.upsert(record)
                added += 1
            elif existing.content_hash != record.content_hash:
                from dataclasses import replace
                record = replace(record, import_batch_id=batch_id)
                self._sr_repo.update_status(existing.source_record_id, "superseded")
                self._deprecate_published_units(existing.source_record_id)
                self._sr_repo.upsert(record)
                updated += 1
            else:
                unchanged += 1

        finished = datetime.now(timezone.utc).isoformat()
        from dataclasses import replace as _replace
        batch = _replace(
            batch,
            status="success",
            finished_at=finished,
            record_count=len(records),
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
