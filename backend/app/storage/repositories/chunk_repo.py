import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class ChunkRepository:
    def __init__(self, path: Path | None = None) -> None:
        self._path = path or (
            Path(__file__).resolve().parents[1] / "chunks" / "chunks.jsonl"
        )

    def list_all(self) -> list[dict[str, Any]]:
        if not self._path.exists():
            return []

        records: list[dict[str, Any]] = []
        for line in self._path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                records.append(json.loads(line))
        return records

    def save(
        self,
        *,
        document_id: str,
        filename: str,
        chunks: list[str],
        file_path: str | None = None,
    ) -> list[dict[str, Any]]:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        created_at = datetime.now(timezone.utc).isoformat()
        records: list[dict[str, Any]] = []
        with self._path.open("a", encoding="utf-8") as handle:
            for index, chunk_text in enumerate(chunks):
                locator_parts = [f"document_id: {document_id}"]
                if file_path:
                    locator_parts.append(f"file_path: {file_path}")
                locator_parts.append(f"chunk: {index + 1}")
                record = {
                    "chunk_id": f"{document_id}-chunk-{index + 1}",
                    "document_id": document_id,
                    "filename": filename,
                    "file_path": file_path,
                    "chunk_index": index,
                    "text": chunk_text,
                    "source_label": filename,
                    "source_locator": " · ".join(locator_parts),
                    "snippet": chunk_text[:160],
                    "created_at": created_at,
                }
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
                records.append(record)
        return records

    def delete_by_document(self, document_id: str) -> int:
        records = self.list_all()
        retained_records = [
            record for record in records if record.get("document_id") != document_id
        ]
        deleted_count = len(records) - len(retained_records)

        if deleted_count == 0:
            return 0

        if retained_records:
            serialized = (
                "\n".join(
                    json.dumps(record, ensure_ascii=False)
                    for record in retained_records
                )
                + "\n"
            )
            self._path.write_text(serialized, encoding="utf-8")
        elif self._path.exists():
            self._path.unlink()

        return deleted_count

    def update_status_by_source_record(
        self, source_record_id: str, lifecycle_status: str
    ) -> list[str]:
        records = self.list_all()
        updated_ids: list[str] = []

        for record in records:
            if record.get("source_record_id") != source_record_id:
                continue
            if record.get("lifecycle_status", "active") == lifecycle_status:
                continue

            record["lifecycle_status"] = lifecycle_status
            chunk_id = str(record.get("chunk_id") or "")
            if chunk_id:
                updated_ids.append(chunk_id)

        if updated_ids:
            serialized = (
                "\n".join(
                    json.dumps(record, ensure_ascii=False) for record in records
                )
                + "\n"
            )
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(serialized, encoding="utf-8")

        return updated_ids
