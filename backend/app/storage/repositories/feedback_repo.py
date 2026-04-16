import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class FeedbackRepository:
    def __init__(self) -> None:
        self._path = (
            Path(__file__).resolve().parents[1] / "feedback" / "feedback_records.jsonl"
        )

    def save(self, record: dict[str, Any]) -> dict[str, Any]:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        enriched_record = {
            **record,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(enriched_record, ensure_ascii=False) + "\n")
        return enriched_record

    def list_recent(self, limit: int = 50) -> list[dict[str, Any]]:
        if not self._path.exists():
            return []

        records = [
            json.loads(line)
            for line in self._path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        records.reverse()
        return records[:limit]
