from datetime import UTC, datetime
from uuid import uuid4

from app.models.entities import DocumentORM
from app.repositories.document_repository import DocumentRepository


class DocumentIngestionService:
    """Handle document upload registration and ingestion kickoff."""

    def __init__(self) -> None:
        self.repository = DocumentRepository()

    def register_upload(self, name: str, content: str, source_type: str = "upload") -> DocumentORM:
        document = DocumentORM(
            document_id=str(uuid4()),
            name=name,
            source_type=source_type,
            status="uploaded",
            created_at=datetime.now(UTC),
            content=content,
            chunks_json=[],
        )
        return self.repository.save(document)
