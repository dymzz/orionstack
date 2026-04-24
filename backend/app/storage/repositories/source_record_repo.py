from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from app.storage.models.source_record import SourceRecord

_STORAGE_DIR = Path(__file__).resolve().parents[1] / "source_records"


class SourceRecordRepo:
    def __init__(self, storage_dir: Path | None = None) -> None:
        self._dir = storage_dir or _STORAGE_DIR
        self._dir.mkdir(parents=True, exist_ok=True)
        self._file = self._dir / "source_records.jsonl"

    def upsert(self, record: SourceRecord) -> None:
        existing = self._find_active_by_system_and_external(record.source_system, record.external_id)
        if existing is not None:
            self._remove(existing.source_record_id)
        self._append(record)

    def get(self, source_record_id: str) -> SourceRecord | None:
        for record in self._iter_all():
            if record.source_record_id == source_record_id:
                return record
        return None

    def list_by_status(self, status: str) -> list[SourceRecord]:
        return [r for r in self._iter_all() if r.status == status]

    def list_by_source_system(self, source_system: str) -> list[SourceRecord]:
        return [r for r in self._iter_all() if r.source_system == source_system]

    def update_status(self, source_record_id: str, status: str) -> None:
        records = list(self._iter_all())
        self._file.write_text("", encoding="utf-8")
        for r in records:
            if r.source_record_id == source_record_id:
                from dataclasses import replace
                r = replace(r, status=status)
            self._append(r)

    def _find_active_by_system_and_external(self, source_system: str, external_id: str) -> SourceRecord | None:
        for r in self._iter_all():
            if r.source_system == source_system and r.external_id == external_id and r.status == "active":
                return r
        return None

    def _find_by_system_and_external(self, source_system: str, external_id: str) -> SourceRecord | None:
        for r in self._iter_all():
            if r.source_system == source_system and r.external_id == external_id:
                return r
        return None

    def _remove(self, source_record_id: str) -> None:
        records = [r for r in self._iter_all() if r.source_record_id != source_record_id]
        self._file.write_text("", encoding="utf-8")
        for r in records:
            self._append(r)

    def _append(self, record: SourceRecord) -> None:
        with open(self._file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")

    def _iter_all(self) -> list[SourceRecord]:
        if not self._file.exists():
            return []
        lines = self._file.read_text(encoding="utf-8").strip().split("\n")
        results: list[SourceRecord] = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            results.append(self._parse(json.loads(line)))
        return results

    @staticmethod
    def _parse(d: dict[str, Any]) -> SourceRecord:
        return SourceRecord(
            source_record_id=d["source_record_id"],
            tenant_id=d.get("tenant_id", "default"),
            source_system=d["source_system"],
            source_object_type=d["source_object_type"],
            external_id=d["external_id"],
            source_locator=d["source_locator"],
            title=d.get("title", ""),
            raw_content=d.get("raw_content", ""),
            content_hash=d["content_hash"],
            source_updated_at=d["source_updated_at"],
            export_batch_id=d["export_batch_id"],
            access_scope=d.get("access_scope", "internal"),
            status=d.get("status", "active"),
            synced_at=d["synced_at"],
            import_batch_id=d.get("import_batch_id"),
        )
