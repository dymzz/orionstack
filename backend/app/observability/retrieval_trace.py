import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.storage.repositories.base_repo import JsonlLock

_logger = logging.getLogger("orionstack.retrieval_trace")


class RetrievalTraceRepository:
    def __init__(self, *, max_count: int = 0) -> None:
        self._path = (
            Path(__file__).resolve().parents[1]
            / "storage"
            / "retrieval_traces"
            / "retrieval_traces.jsonl"
        )
        self._max_count = max_count
        self._lock = JsonlLock(self._path)

    def save(self, trace: dict[str, Any]) -> dict[str, Any]:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        enriched_trace = {
            **trace,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        with self._lock, self._path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(enriched_trace, ensure_ascii=False) + "\n")
        self._truncate_if_needed()
        trace_id = enriched_trace.get("trace_id", "?")
        _logger.debug("retrieval_trace_saved trace_id=%s", trace_id)
        return enriched_trace

    def get_by_trace_id(self, trace_id: str) -> dict[str, Any] | None:
        if not self._path.exists():
            return None

        for line in reversed(self._path.read_text(encoding="utf-8").splitlines()):
            if not line.strip():
                continue
            record = json.loads(line)
            if str(record.get("trace_id", "")) == trace_id:
                return record
        return None

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

    def _truncate_if_needed(self) -> None:
        if self._max_count <= 0 or not self._path.exists():
            return

        with self._lock:
            lines = self._path.read_text(encoding="utf-8").splitlines()
            non_empty = [line for line in lines if line.strip()]
            if len(non_empty) <= self._max_count:
                return

            retained = non_empty[-self._max_count :]
            self._path.write_text("\n".join(retained) + "\n", encoding="utf-8")
