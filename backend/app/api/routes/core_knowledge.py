"""Stable query entry and scoped document knowledge lifecycle endpoints."""

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response, JSONResponse
from app.workbench.contracts import WorkbenchFailureResponse

from app.api.core_access import require_core_access
from app.api.core_contracts import (DocumentListResponse, DocumentWriteResponse, DocumentRevocationResponse,
                                    CoreAccessResponse, CorePermissions)
from app.config.core_settings import CoreConfigurationError
from app.knowledge.contracts import AccessContext
from app.knowledge.document_ingestion import DocumentKnowledgeService
from app.knowledge.postgres import DatabaseUnavailable
from app.providers.http import ProviderError
from app.retrieval.postgres_vector import EmbeddingWriteConflict
from app.services.core_query_service import CoreQueryRequest, CoreQueryResponse, CoreQueryService

router = APIRouter(prefix="/api",tags=["core-knowledge"])
CORE_ERRORS = {
    401: {"description":"Authentication required"},
    403: {"description":"Account or document scope does not permit this operation"},
    503: {"description":"Core configuration, database or provider is unavailable",'model':WorkbenchFailureResponse},
}
DOCUMENT_ERRORS = {
    **CORE_ERRORS,
    400: {"description":"Invalid file or document input"},
    404: {"description":"Document is unavailable in the caller's current scope"},
    409: {"description":"Document changed or was revoked during indexing"},
}


def get_core_query_service():
    return CoreQueryService()


def get_core_document_service():
    return DocumentKnowledgeService()


def translate_error(error):
    if isinstance(error,PermissionError):
        return HTTPException(status_code=403,detail="Insufficient document permissions")
    if isinstance(error,LookupError):
        return HTTPException(status_code=404,detail="Document is unavailable")
    if isinstance(error,EmbeddingWriteConflict):
        return HTTPException(status_code=409,detail="Document changed during indexing; inspect its current version")
    if isinstance(error,(DatabaseUnavailable,CoreConfigurationError,ProviderError)):
        feedback=getattr(error,'execution_feedback',None)
        if feedback is not None:
            headers={'X-Core-Request-ID':feedback.request_id}
            if feedback.retrieval_event_id:
                headers['X-Retrieval-Event-ID']=feedback.retrieval_event_id
            return HTTPException(status_code=503,detail='Core query dependency is unavailable',headers=headers)
        return HTTPException(status_code=503,detail="Core query dependency is unavailable")
    return HTTPException(status_code=400,detail="Invalid document or query input")


def feedback_error_response(error):
    failure=translate_error(error)
    return JSONResponse(status_code=failure.status_code,headers=failure.headers,
        content={'detail':failure.detail,'execution_feedback':error.execution_feedback.model_dump(mode='json')})


@router.get("/access-context",response_model=CoreAccessResponse,responses=CORE_ERRORS)
def access_context(access: AccessContext = Depends(require_core_access)):
    return CoreAccessResponse(**access.model_dump(),permissions=CorePermissions(
        documents_maintain="admin" in access.roles))


@router.post("/query",response_model=CoreQueryResponse,responses={**CORE_ERRORS,400:{"description":"Unsupported or invalid query scope"}})
def query_knowledge(payload: CoreQueryRequest,access: AccessContext = Depends(require_core_access),
                    service=Depends(get_core_query_service)):
    try:
        return service.query(payload,access)
    except (PermissionError,ValueError,DatabaseUnavailable,ProviderError,CoreConfigurationError) as error:
        if getattr(error,'execution_feedback',None) is not None:
            return feedback_error_response(error)
        failure = translate_error(error)
        if getattr(error,"request_id",None):
            failure.headers = {"X-Core-Request-ID":error.request_id}
            if getattr(error,'retrieval_event_id',None):
                failure.headers['X-Retrieval-Event-ID']=error.retrieval_event_id
        raise failure from None


@router.get("/documents",response_model=DocumentListResponse,responses=CORE_ERRORS)
def list_documents(access: AccessContext = Depends(require_core_access),service=Depends(get_core_document_service)):
    try:
        return {"items":service.list_documents(access)}
    except (DatabaseUnavailable,CoreConfigurationError) as error:
        raise translate_error(error) from None


@router.post("/documents",response_model=DocumentWriteResponse,response_model_exclude_none=True,responses=DOCUMENT_ERRORS)
async def upload_document(file: UploadFile = File(...),document_id: str | None = Form(default=None),
                          access_scope: str = Form(default="internal"),access: AccessContext = Depends(require_core_access),
                          service=Depends(get_core_document_service)):
    if "admin" not in access.roles or access_scope not in access.allowed_scopes:
        raise HTTPException(status_code=403,detail="Document maintenance requires curator permissions")
    from app.dataops.legacy import require_legacy_upload
    require_legacy_upload()
    data = await file.read(10*1024*1024+1)
    try:
        return await run_in_threadpool(service.ingest,file.filename or "document",data,access,
            document_id=document_id,scope=access_scope,content_type=file.content_type or "application/octet-stream")
    except (PermissionError,ValueError,DatabaseUnavailable,ProviderError,CoreConfigurationError,EmbeddingWriteConflict) as error:
        raise translate_error(error) from None


@router.post("/documents/{document_id}/index",response_model=DocumentWriteResponse,response_model_exclude_none=True,responses=DOCUMENT_ERRORS)
def index_document(document_id: str,document_version: str = Form(...),access: AccessContext = Depends(require_core_access),
                   service=Depends(get_core_document_service)):
    try:
        return service.index(document_id,document_version,access)
    except (PermissionError,LookupError,ValueError,DatabaseUnavailable,ProviderError,CoreConfigurationError,EmbeddingWriteConflict) as error:
        raise translate_error(error) from None


@router.get("/documents/{document_id}/content",response_class=Response,responses={
    **CORE_ERRORS,
    200: {"description":"Authorized active original file returned as an attachment; MIME type follows filename",
          "content":{"application/octet-stream":{"schema":{"type":"string","format":"binary"}}}},
    404: {"description":"Current authorized original file is unavailable"},
})
def read_document(document_id: str,document_version: str | None = None,
                  access: AccessContext = Depends(require_core_access),service=Depends(get_core_document_service)):
    from urllib.parse import quote
    import mimetypes
    try:
        filename,data = service.read_file(document_id,document_version,access)
        return Response(data,media_type=mimetypes.guess_type(filename)[0] or "application/octet-stream",
                        headers={"Content-Disposition": "attachment; filename*=UTF-8''"+quote(filename,safe="")})
    except (LookupError,DatabaseUnavailable,CoreConfigurationError) as error:
        raise translate_error(error) from None


@router.delete("/documents/{document_id}",response_model=DocumentRevocationResponse,responses={**CORE_ERRORS,404:{"description":"Document is unavailable in the caller's scope"}})
def revoke_document(document_id: str,access: AccessContext = Depends(require_core_access),service=Depends(get_core_document_service)):
    try:
        return service.revoke(document_id,access)
    except (PermissionError,LookupError,DatabaseUnavailable,CoreConfigurationError) as error:
        raise translate_error(error) from None
