import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class HardCasesRepository:
    def __init__(self, *, max_count: int = 0) -> None:
        self._path = (
            Path(__file__).resolve().parents[1]
            / "storage"
            / "hard_cases"
            / "hard_cases.jsonl"
        )
        self._max_count = max_count

    def upsert(self, item: dict[str, Any]) -> dict[str, Any]:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        records = self._load_all()

        trace_id = str(item.get("trace_id", ""))
        existing = next(
            (record for record in records if str(record.get("trace_id", "")) == trace_id),
            None,
        )
        if existing is None:
            enriched_item = {
                **item,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            records.append(enriched_item)
        else:
            existing.update(
                {
                    key: value
                    for key, value in item.items()
                    if value is not None and value != []
                }
            )
            enriched_item = existing

        self._write_all(records)
        self._truncate_if_needed()
        return enriched_item

    def list_recent(self, limit: int = 50) -> list[dict[str, Any]]:
        records = self._load_all()
        records.reverse()
        return records[:limit]

    def _load_all(self) -> list[dict[str, Any]]:
        if not self._path.exists():
            return []
        return [
            json.loads(line)
            for line in self._path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def _write_all(self, records: list[dict[str, Any]]) -> None:
        if not records:
            self._path.write_text("", encoding="utf-8")
            return
        serialized = "\n".join(json.dumps(record, ensure_ascii=False) for record in records)
        self._path.write_text(serialized + "\n", encoding="utf-8")

    def _truncate_if_needed(self) -> None:
        if self._max_count <= 0:
            return
        records = self._load_all()
        if len(records) <= self._max_count:
            return
        self._write_all(records[-self._max_count :])
