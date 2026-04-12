import json

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse

from app.core.request_context import get_current_user_context
from app.governance.authorization import require_permission
from app.governance.audit_service import AuditService
from app.api.schemas.document import (
    DeleteDocumentResponse,
    DocumentListResponse,
    DocumentResponse,
    IndexJobResponse,
    ReindexDocumentResponse,
)
from app.knowledge.indexing.index_dispatcher import index_dispatcher
from app.knowledge.ingestion.document_ingestion_service import DocumentIngestionService
from app.knowledge.ingestion.document_parser import (
    DocumentParser,
    MissingParserDependencyError,
    UnsupportedDocumentTypeError,
)
from app.repositories.document_repository import DocumentRepository
from app.repositories.index_job_repository import IndexJobRepository

router = APIRouter(tags=["documents"])
repository = DocumentRepository()
index_job_repository = IndexJobRepository()
ingestion_service = DocumentIngestionService()
document_parser = DocumentParser()
audit_service = AuditService()


def build_index_job_response(job) -> IndexJobResponse | None:
    if job is None:
        return None
    return IndexJobResponse(
        job_id=job.job_id,
        document_id=job.document_id,
        status=job.status,
        progress_pct=job.progress_pct,
        error_code=job.error_code,
        error_message=job.error_message,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
    )


def build_document_response(document) -> DocumentResponse:
    latest_job = index_job_repository.get_latest_for_document(document.document_id)
    return DocumentResponse(
        document_id=document.document_id,
        name=document.name,
        status=document.status,
        source_type=document.source_type,
        created_at=document.created_at,
        latest_index_job=build_index_job_response(latest_job),
    )


@router.post("/documents/upload", response_model=DocumentResponse)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    name: str = Form(...),
    source_type: str = Form(default="upload"),
) -> DocumentResponse:
    user_context = get_current_user_context(request)
    owner_user_id = user_context.user_id
    require_permission(user_context, resource="document", action="write")
    payload = await file.read()
    try:
        content = document_parser.parse(
            filename=file.filename,
            content_type=file.content_type,
            payload=payload,
        )
    except UnsupportedDocumentTypeError as exc:
        audit_service.log(
            owner_user_id=owner_user_id,
            event_type="document_upload_rejected",
            payload={"filename": file.filename or "", "reason": "unsupported_type"},
        )
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    except MissingParserDependencyError as exc:
        audit_service.log(
            owner_user_id=owner_user_id,
            event_type="document_upload_failed",
            payload={"filename": file.filename or "", "reason": "missing_dependency"},
        )
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    document = ingestion_service.register_upload(
        name=name or file.filename or "Untitled document",
        content=content,
        source_type=source_type,
        owner_user_id=owner_user_id,
    )
    index_dispatcher.submit(document.document_id)
    refreshed_document = repository.get(document.document_id, owner_user_id=owner_user_id)
    if refreshed_document is None:
        raise HTTPException(status_code=500, detail="Document upload failed")
    audit_service.log(
        owner_user_id=owner_user_id,
        event_type="document_uploaded",
        payload={"document_id": refreshed_document.document_id, "source_type": refreshed_document.source_type},
    )

    return build_document_response(refreshed_document)


@router.get("/documents", response_model=DocumentListResponse)
def list_documents(request: Request) -> DocumentListResponse:
    user_context = get_current_user_context(request)
    owner_user_id = user_context.user_id
    require_permission(user_context, resource="document", action="read")
    return DocumentListResponse(
        items=[
            build_document_response(document)
            for document in repository.list(owner_user_id=owner_user_id)
        ]
    )


@router.get("/documents/{document_id}", response_model=DocumentResponse)
def get_document(document_id: str, request: Request) -> DocumentResponse:
    user_context = get_current_user_context(request)
    owner_user_id = user_context.user_id
    require_permission(user_context, resource="document", action="read")
    document = repository.get(document_id, owner_user_id=owner_user_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    return build_document_response(document)


@router.get("/documents/{document_id}/index-job", response_model=IndexJobResponse)
def get_latest_index_job(document_id: str, request: Request) -> IndexJobResponse:
    user_context = get_current_user_context(request)
    owner_user_id = user_context.user_id
    require_permission(user_context, resource="document", action="read")
    document = repository.get(document_id, owner_user_id=owner_user_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    job = index_job_repository.get_latest_for_document(document_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Index job not found")
    return build_index_job_response(job)


@router.get("/index-jobs/{job_id}", response_model=IndexJobResponse)
def get_index_job(job_id: str, request: Request) -> IndexJobResponse:
    user_context = get_current_user_context(request)
    owner_user_id = user_context.user_id
    require_permission(user_context, resource="document", action="read")
    job = index_job_repository.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Index job not found")
    document = repository.get(job.document_id, owner_user_id=owner_user_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Index job not found")
    return build_index_job_response(job)


@router.get("/index-jobs/{job_id}/stream")
def stream_index_job(job_id: str, request: Request) -> StreamingResponse:
    user_context = get_current_user_context(request)
    owner_user_id = user_context.user_id
    require_permission(user_context, resource="document", action="read")
    job = index_job_repository.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Index job not found")
    document = repository.get(job.document_id, owner_user_id=owner_user_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Index job not found")

    def event_generator():
        queue = index_dispatcher.subscribe(job_id)
        try:
            while True:
                event = index_dispatcher.next_event(queue, timeout=15.0)
                if event is None:
                    yield ": heartbeat\n\n"
                    continue
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                if event.get("status") in {"indexed", "failed", "missing"}:
                    break
        finally:
            index_dispatcher.unsubscribe(job_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.delete("/documents/{document_id}", response_model=DeleteDocumentResponse)
def delete_document(document_id: str, request: Request) -> DeleteDocumentResponse:
    user_context = get_current_user_context(request)
    owner_user_id = user_context.user_id
    require_permission(user_context, resource="document", action="write")
    deleted = repository.delete(document_id, owner_user_id=owner_user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found")
    audit_service.log(
        owner_user_id=owner_user_id,
        event_type="document_deleted",
        payload={"document_id": document_id},
    )
    return DeleteDocumentResponse(ok=True, document_id=document_id)


@router.post("/documents/{document_id}/reindex", response_model=ReindexDocumentResponse)
def reindex_document(document_id: str, request: Request) -> ReindexDocumentResponse:
    user_context = get_current_user_context(request)
    owner_user_id = user_context.user_id
    require_permission(user_context, resource="document", action="write")
    document = repository.get(document_id, owner_user_id=owner_user_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    job = index_dispatcher.submit(document_id)
    audit_service.log(
        owner_user_id=owner_user_id,
        event_type="document_reindexed",
        payload={"document_id": document_id, "job_id": job.job_id if job else ""},
    )
    return ReindexDocumentResponse(
        document_id=document_id,
        status=job.status,
        job=build_index_job_response(job),
    )
