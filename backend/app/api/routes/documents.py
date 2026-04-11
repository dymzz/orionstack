from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, File, Form, UploadFile

from app.api.schemas.document import DocumentResponse

router = APIRouter(tags=["documents"])


@router.post("/documents/upload", response_model=DocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    name: str = Form(...),
    source_type: str = Form(default="upload"),
) -> DocumentResponse:
    return DocumentResponse(
        document_id=str(uuid4()),
        name=name or file.filename,
        status="uploaded",
        source_type=source_type,
        created_at=datetime.utcnow(),
    )


@router.get("/documents")
def list_documents() -> dict:
    return {"items": []}


@router.get("/documents/{document_id}")
def get_document(document_id: str) -> dict:
    return {"document_id": document_id}


@router.delete("/documents/{document_id}")
def delete_document(document_id: str) -> dict:
    return {"ok": True, "document_id": document_id}


@router.post("/documents/{document_id}/reindex")
def reindex_document(document_id: str) -> dict:
    return {"document_id": document_id, "status": "indexing"}
