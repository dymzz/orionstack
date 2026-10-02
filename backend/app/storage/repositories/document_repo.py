import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.storage.repositories.base_repo import JsonlLock


class DocumentRepository:
    def __init__(self) -> None:
        self._meta_path = (
            Path(__file__).resolve().parents[1] / "documents" / "documents.jsonl"
        )
        self._upload_dir = Path(__file__).resolve().parents[1] / "uploads"
        self._lock = JsonlLock(self._meta_path)

    def list_all(self) -> list[dict[str, Any]]:
        if not self._meta_path.exists():
            return []

        records: list[dict[str, Any]] = []
        for line in self._meta_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                records.append(json.loads(line))
        return records

    def save(
        self,
        *,
        document_id: str,
        filename: str,
        content_type: str,
        data: bytes,
        text_length: int,
        chunk_count: int,
    ) -> dict[str, Any]:
        self._upload_dir.mkdir(parents=True, exist_ok=True)
        self._meta_path.parent.mkdir(parents=True, exist_ok=True)

        stored_path = self._upload_dir / f"{document_id}_{filename}"
        stored_path.write_bytes(data)

        created_at = datetime.now(timezone.utc).isoformat()
        record = {
            "document_id": document_id,
            "filename": filename,
            "content_type": content_type,
            "size_bytes": len(data),
            "storage_path": str(stored_path),
            "created_at": created_at,
            "text_length": text_length,
            "chunk_count": chunk_count,
        }
        with self._lock, self._meta_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        return record

    def delete(self, document_id: str) -> dict[str, Any] | None:
        with self._lock:
            records = self.list_all()
            retained_records: list[dict[str, Any]] = []
            deleted_record: dict[str, Any] | None = None

            for record in records:
                if record.get("document_id") == document_id and deleted_record is None:
                    deleted_record = record
                    continue
                retained_records.append(record)

            if deleted_record is None:
                return None

            if retained_records:
                serialized = (
                    "\n".join(
                        json.dumps(record, ensure_ascii=False)
                        for record in retained_records
                    )
                    + "\n"
                )
                self._meta_path.write_text(serialized, encoding="utf-8")
            elif self._meta_path.exists():
                self._meta_path.unlink()

        storage_path = Path(str(deleted_record.get("storage_path", "")))
        if storage_path.exists():
            storage_path.unlink()

        return deleted_record
