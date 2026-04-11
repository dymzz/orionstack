from datetime import datetime
from pydantic import BaseModel


class DocumentResponse(BaseModel):
    document_id: str
    name: str
    status: str
    source_type: str = "upload"
    created_at: datetime
