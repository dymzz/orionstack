import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class ChatRecordRepository:
    def __init__(self) -> None:
        self._path = (
            Path(__file__).resolve().parents[1] / "chat_records" / "chat_records.jsonl"
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

    def attach_feedback(
        self, *, trace_id: str, feedback_label: str, feedback_created_at: str
    ) -> bool:
        if not self._path.exists():
            return False

        records = [
            json.loads(line)
            for line in self._path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        updated = False
        for record in reversed(records):
            if str(record.get("trace_id", "")) == trace_id:
                record["feedback_label"] = feedback_label
                record["feedback_created_at"] = feedback_created_at
                updated = True
                break

        if not updated:
            return False

        serialized = (
            "\n".join(json.dumps(record, ensure_ascii=False) for record in records)
            + "\n"
        )
        self._path.write_text(serialized, encoding="utf-8")
        return True
