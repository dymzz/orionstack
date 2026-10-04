from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.api.auth import require_admin
from app.schemas.document import (
    DocumentDeleteResponse,
    DocumentListResponse,
    DocumentUploadResponse,
)
from app.services.document_service import DocumentService

router = APIRouter(
    prefix="/api/v1/documents",
    tags=["documents"],
    dependencies=[Depends(require_admin)],
)
service = DocumentService()


def get_document_service() -> DocumentService:
    return service


@router.get("", response_model=DocumentListResponse)
def list_documents() -> DocumentListResponse:
    return service.list_documents()


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(file: UploadFile = File(...)) -> DocumentUploadResponse:
    from app.dataops.legacy import require_legacy_upload
    require_legacy_upload()
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
