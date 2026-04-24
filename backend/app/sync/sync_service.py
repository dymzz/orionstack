from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.sync.sync_parser import parse_export_file
from app.sync.tombstone_handler import handle_tombstone
from app.storage.models.source_record import SourceRecord
from app.storage.models.import_batch import ImportBatch
from app.storage.repositories.source_record_repo import SourceRecordRepo
from app.storage.repositories.import_batch_repo import ImportBatchRepo


class SyncService:
    def __init__(
        self,
        source_record_repo: SourceRecordRepo,
        import_batch_repo: ImportBatchRepo,
    ) -> None:
        self._sr_repo = source_record_repo
        self._ib_repo = import_batch_repo

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
            existing = self._sr_repo._find_by_system_and_external(
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
