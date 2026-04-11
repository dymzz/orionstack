from datetime import datetime
from pydantic import BaseModel


class IndexJobResponse(BaseModel):
    job_id: str
    document_id: str
    status: str
    progress_pct: int
    error_code: str = ""
    error_message: str = ""
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class DocumentResponse(BaseModel):
    document_id: str
    name: str
    status: str
    source_type: str = "upload"
    created_at: datetime
    latest_index_job: IndexJobResponse | None = None


class DocumentListResponse(BaseModel):
    items: list[DocumentResponse]


class DeleteDocumentResponse(BaseModel):
    ok: bool
    document_id: str


class ReindexDocumentResponse(BaseModel):
    document_id: str
    status: str
    job: IndexJobResponse | None = None
