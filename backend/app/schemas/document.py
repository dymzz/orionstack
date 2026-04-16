from typing import Literal

from pydantic import BaseModel


class DocumentListItem(BaseModel):
    document_id: str
    filename: str
    content_type: str
    size_bytes: int
    created_at: str
    text_length: int
    chunk_count: int


class DocumentUploadResponse(BaseModel):
    status: Literal["uploaded"]
    document_id: str
    filename: str
    content_type: str
    size_bytes: int
    created_at: str
    text_length: int
    chunk_count: int


class DocumentListResponse(BaseModel):
    items: list[DocumentListItem]


class DocumentDeleteResponse(BaseModel):
    status: Literal["deleted"]
    document_id: str
