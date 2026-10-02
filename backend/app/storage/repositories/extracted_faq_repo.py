from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.storage.repositories.base_repo import JsonlLock

_STORAGE_DIR = Path(__file__).resolve().parents[1] / "extracted_faqs"


class ExtractedFaqRepo:
    def __init__(self, storage_dir: Path | None = None) -> None:
        self._dir = storage_dir or _STORAGE_DIR
        self._dir.mkdir(parents=True, exist_ok=True)
        self._file = self._dir / "extracted_faqs.jsonl"
        self._lock = JsonlLock(self._file)

    def upsert(self, item: dict[str, Any]) -> None:
        item = dict(item)
        unit_id = str(item.get("unit_id") or item.get("id") or "").strip()
        if not unit_id:
            raise ValueError("Extracted FAQ requires a unit_id")
        item["unit_id"] = unit_id
        with self._lock:
            existing_idx = None
            items = self._list_all_raw()
            for i, existing in enumerate(items):
                if (existing.get("unit_id") or existing.get("id")) == unit_id:
                    existing_idx = i
                    break
            if existing_idx is not None:
                items[existing_idx] = item
            else:
                items.append(item)
            self._write_all(items)

    def list_all(self) -> list[dict[str, Any]]:
        return self._list_all_raw()

    def update_status_by_source_record(
        self, source_record_id: str, lifecycle_status: str
    ) -> list[str]:
        with self._lock:
            items = self._list_all_raw()
            updated_ids: list[str] = []
            for item in items:
                if item.get("source_record_id") != source_record_id:
                    continue
                if item.get("lifecycle_status", "active") == lifecycle_status:
                    continue
                item["lifecycle_status"] = lifecycle_status
                unit_id = str(item.get("unit_id") or item.get("id") or "")
                if unit_id:
                    updated_ids.append(unit_id)
            if updated_ids:
                self._write_all(items)
        return updated_ids

    def _list_all_raw(self) -> list[dict[str, Any]]:
        if not self._file.exists():
            return []
        results: list[dict[str, Any]] = []
        known_ids: dict[str, int] = {}
        for line in self._file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                item = json.loads(line)
                unit_id = item.get("unit_id") or item.get("id")
                if unit_id and unit_id in known_ids:
                    results[known_ids[unit_id]] = item
                else:
                    if unit_id:
                        known_ids[unit_id] = len(results)
                    results.append(item)
        return results

    def _write_all(self, items: list[dict[str, Any]]) -> None:
        serialized = "\n".join(json.dumps(item, ensure_ascii=False) for item in items)
        self._file.write_text(serialized + "\n", encoding="utf-8")
