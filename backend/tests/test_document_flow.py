import json
from pathlib import Path
import sys

from fastapi.testclient import TestClient

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.api.routes import documents as documents_route
from main import app


def _configure_document_storage(tmp_path: Path) -> None:
    documents_route.service._repository._meta_path = tmp_path / "documents.jsonl"
    documents_route.service._repository._upload_dir = tmp_path / "uploads"
    documents_route.service._chunk_repository._path = tmp_path / "chunks.jsonl"


def test_document_upload_registers_file_and_metadata(tmp_path, admin_headers) -> None:
    _configure_document_storage(tmp_path)

    client = TestClient(app)
    response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("guide.txt", b"hello document", "text/plain")},
        headers=admin_headers,
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

    saved_lines = (
        (tmp_path / "documents.jsonl").read_text(encoding="utf-8").splitlines()
    )
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
    assert (
        chunk_record["source_locator"]
        == f"document_id: {payload['document_id']} · file_path: uploads/{payload['document_id']}_guide.txt · chunk: 1"
    )
    assert chunk_record["snippet"] == "hello document"


def test_document_list_returns_uploaded_documents_in_reverse_created_order(
    tmp_path,
    admin_headers,
) -> None:
    _configure_document_storage(tmp_path)

    client = TestClient(app)
    first_response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("first.txt", b"first document text", "text/plain")},
        headers=admin_headers,
    )
    second_response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("second.txt", b"second document body", "text/plain")},
        headers=admin_headers,
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200

    response = client.get("/api/v1/documents", headers=admin_headers)

    assert response.status_code == 200
    payload = response.json()
    assert [item["filename"] for item in payload["items"]] == [
        "second.txt",
        "first.txt",
    ]
    assert payload["items"][0]["text_length"] == len("second document body")
    assert payload["items"][0]["chunk_count"] == 1
    assert payload["items"][1]["text_length"] == len("first document text")
    assert payload["items"][1]["chunk_count"] == 1


def test_document_delete_removes_file_metadata_and_chunks(tmp_path, admin_headers) -> None:
    _configure_document_storage(tmp_path)

    client = TestClient(app)
    upload_response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("guide.txt", b"hello document", "text/plain")},
        headers=admin_headers,
    )

    assert upload_response.status_code == 200
    document_id = upload_response.json()["document_id"]
    uploaded_file = tmp_path / "uploads" / f"{document_id}_guide.txt"
    assert uploaded_file.exists()

    delete_response = client.delete(
        f"/api/v1/documents/{document_id}", headers=admin_headers
    )

    assert delete_response.status_code == 200
    assert delete_response.json() == {"status": "deleted", "document_id": document_id}
    assert not uploaded_file.exists()
    assert not (tmp_path / "documents.jsonl").exists()
    assert not (tmp_path / "chunks.jsonl").exists()


def test_document_delete_returns_404_for_unknown_document(tmp_path, admin_headers) -> None:
    _configure_document_storage(tmp_path)

    client = TestClient(app)
    response = client.delete("/api/v1/documents/doc-missing", headers=admin_headers)

    assert response.status_code == 404
    assert response.json()["detail"] == "文档不存在"


def test_document_upload_rejects_unsupported_suffix(admin_headers) -> None:
    client = TestClient(app)
    response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("guide.exe", b"bad", "application/octet-stream")},
        headers=admin_headers,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "当前仅支持 .txt / .md / .pdf / .docx 文件"


def test_documents_endpoints_require_auth() -> None:
    client = TestClient(app)

    assert client.get("/api/v1/documents").status_code == 401
    assert client.post(
        "/api/v1/documents/upload",
        files={"file": ("test.txt", b"data", "text/plain")},
    ).status_code == 401
    assert client.delete("/api/v1/documents/doc-x").status_code == 401


def test_documents_endpoints_reject_user_role() -> None:
    client = TestClient(app)
    login = client.post("/api/v1/auth/login", json={"username": "test", "password": "test"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    assert client.get("/api/v1/documents", headers=headers).status_code == 403
    assert client.post(
        "/api/v1/documents/upload",
        files={"file": ("test.txt", b"data", "text/plain")},
        headers=headers,
    ).status_code == 403
    assert client.delete("/api/v1/documents/doc-x", headers=headers).status_code == 403