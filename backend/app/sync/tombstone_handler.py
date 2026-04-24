from __future__ import annotations

from app.storage.repositories.source_record_repo import SourceRecordRepo
from app.storage.repositories.import_batch_repo import ImportBatchRepo
from app.storage.models.import_batch import ImportBatch


def handle_tombstone(
    source_record_id: str,
    new_status: str,
    source_record_repo: SourceRecordRepo,
) -> list[str]:
    source_record_repo.update_status(source_record_id, new_status)
    return [source_record_id]
