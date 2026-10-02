from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.storage.models.import_batch import ImportBatch
from app.storage.repositories.base_repo import JsonlLock

_STORAGE_DIR = Path(__file__).resolve().parents[1] / "import_batches"


class ImportBatchRepo:
    def __init__(self, storage_dir: Path | None = None) -> None:
        self._dir = storage_dir or _STORAGE_DIR
        self._dir.mkdir(parents=True, exist_ok=True)
        self._file = self._dir / "import_batches.jsonl"
        self._lock = JsonlLock(self._file)

    def create(self, batch: ImportBatch) -> None:
        with self._lock:
            self._append(batch)

    def get(self, import_batch_id: str) -> ImportBatch | None:
        for b in self._iter_all():
            if b.import_batch_id == import_batch_id:
                return b
        return None

    def update(self, batch: ImportBatch) -> None:
        with self._lock:
            batches = [b for b in self._iter_all() if b.import_batch_id != batch.import_batch_id]
            self._file.write_text("", encoding="utf-8")
            for b in batches:
                self._append(b)
            self._append(batch)

    def list_by_source_system(self, source_system: str) -> list[ImportBatch]:
        return [b for b in self._iter_all() if b.source_system == source_system]

    def _append(self, batch: ImportBatch) -> None:
        with open(self._file, "a", encoding="utf-8") as f:
            f.write(json.dumps(batch.to_dict(), ensure_ascii=False) + "\n")

    def _iter_all(self) -> list[ImportBatch]:
        if not self._file.exists():
            return []
        lines = self._file.read_text(encoding="utf-8").strip().split("\n")
        results: list[ImportBatch] = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            results.append(self._parse(json.loads(line)))
        return results

    @staticmethod
    def _parse(d: dict[str, Any]) -> ImportBatch:
        return ImportBatch(
            import_batch_id=d["import_batch_id"],
            tenant_id=d.get("tenant_id", "default"),
            source_system=d["source_system"],
            mode=d["mode"],
            started_at=d["started_at"],
            status=d.get("status", "running"),
            finished_at=d.get("finished_at"),
            record_count=d.get("record_count", 0),
            error_summary=d.get("error_summary"),
        )
