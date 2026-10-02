import json
from pathlib import Path
from typing import Any

from app.storage.repositories.base_repo import JsonlLock


class FAQRepository:
    def __init__(self, path: Path | None = None) -> None:
        self._path = path or (
            Path(__file__).resolve().parents[1] / "seed" / "mock_faq.json"
        )
        self._lock = JsonlLock(self._path)

    def list_all(self) -> list[dict[str, Any]]:
        if not self._path.exists():
            return []
        return json.loads(self._path.read_text(encoding="utf-8"))

    def update_status_by_source_record(
        self, source_record_id: str, lifecycle_status: str
    ) -> list[str]:
        with self._lock:
            items = self.list_all()
            updated_ids: list[str] = []

            for item in items:
                if item.get("source_record_id") != source_record_id:
                    continue
                if item.get("lifecycle_status", "active") == lifecycle_status:
                    continue

                item["lifecycle_status"] = lifecycle_status
                unit_id = str(item.get("id") or "")
                if unit_id:
                    updated_ids.append(unit_id)

            if updated_ids:
                self._path.parent.mkdir(parents=True, exist_ok=True)
                self._path.write_text(
                    json.dumps(items, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )

        return updated_ids
