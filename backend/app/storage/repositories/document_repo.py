import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class DocumentRepository:
    def __init__(self) -> None:
        self._meta_path = Path(__file__).resolve().parents[1] / "documents" / "documents.jsonl"
        self._upload_dir = Path(__file__).resolve().parents[1] / "uploads"

    def save(self, *, document_id: str, filename: str, content_type: str, data: bytes) -> dict[str, Any]:
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
        }
        with self._meta_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        return record
