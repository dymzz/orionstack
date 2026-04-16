from fastapi import APIRouter, File, HTTPException, UploadFile

from app.schemas.document import (
    DocumentDeleteResponse,
    DocumentListResponse,
    DocumentUploadResponse,
)
from app.services.document_service import DocumentService

router = APIRouter(prefix="/api/documents", tags=["documents"])
service = DocumentService()


@router.get("", response_model=DocumentListResponse)
def list_documents() -> DocumentListResponse:
    return service.list_documents()


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(file: UploadFile = File(...)) -> DocumentUploadResponse:
    try:
        return await service.register_upload(file)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.delete("/{document_id}", response_model=DocumentDeleteResponse)
def delete_document(document_id: str) -> DocumentDeleteResponse:
    try:
        return service.delete_document(document_id)
    except LookupError as error:
        raise HTTPException(status_code=404, detail="文档不存在") from error
