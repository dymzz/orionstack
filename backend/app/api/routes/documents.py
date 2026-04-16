from fastapi import APIRouter, File, HTTPException, UploadFile

from app.schemas.document import DocumentUploadResponse
from app.services.document_service import DocumentService

router = APIRouter(prefix="/api/documents", tags=["documents"])
service = DocumentService()


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(file: UploadFile = File(...)) -> DocumentUploadResponse:
    try:
        return await service.register_upload(file)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
