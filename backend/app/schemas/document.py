from typing import Literal

from pydantic import BaseModel


class DocumentUploadResponse(BaseModel):
    status: Literal["uploaded"]
    document_id: str
    filename: str
    content_type: str
    size_bytes: int
    created_at: str
    text_length: int
    chunk_count: int
