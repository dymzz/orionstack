import json
from pathlib import Path
import sys

from fastapi.testclient import TestClient

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.api.routes import documents as documents_route
from main import app


def test_document_upload_registers_file_and_metadata(tmp_path) -> None:
    documents_route.service._repository._meta_path = tmp_path / "documents.jsonl"
    documents_route.service._repository._upload_dir = tmp_path / "uploads"
    documents_route.service._chunk_repository._path = tmp_path / "chunks.jsonl"

    client = TestClient(app)
    response = client.post(
        "/api/documents/upload",
        files={"file": ("guide.txt", b"hello document", "text/plain")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "uploaded"
    assert payload["document_id"].startswith("doc-")
    assert payload["filename"] == "guide.txt"
    assert payload["content_type"] == "text/plain"
    assert payload["size_bytes"] == len(b"hello document")
    assert payload["created_at"]
    assert payload["text_length"] == len("hello document")
    assert payload["chunk_count"] == 1

    saved_lines = (tmp_path / "documents.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(saved_lines) == 1
    record = json.loads(saved_lines[0])
    assert record["document_id"] == payload["document_id"]
    assert record["filename"] == "guide.txt"
    assert record["size_bytes"] == len(b"hello document")

    stored_path = Path(record["storage_path"])
    assert stored_path.exists()
    assert stored_path.read_bytes() == b"hello document"

    chunk_lines = (tmp_path / "chunks.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(chunk_lines) == 1
    chunk_record = json.loads(chunk_lines[0])
    assert chunk_record["document_id"] == payload["document_id"]
    assert chunk_record["filename"] == "guide.txt"
    assert chunk_record["file_path"] == f"uploads/{payload['document_id']}_guide.txt"
    assert chunk_record["chunk_index"] == 0
    assert chunk_record["text"] == "hello document"
    assert chunk_record["source_label"] == "guide.txt"
    assert chunk_record["source_locator"] == f"document_id: {payload['document_id']} · file_path: uploads/{payload['document_id']}_guide.txt · chunk: 1"
    assert chunk_record["snippet"] == "hello document"


def test_document_upload_rejects_unsupported_suffix() -> None:
    client = TestClient(app)
    response = client.post(
        "/api/documents/upload",
        files={"file": ("guide.exe", b"bad", "application/octet-stream")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "当前仅支持 .txt / .md / .pdf / .docx 文件"
