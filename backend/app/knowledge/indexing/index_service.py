class IndexService:
    """Build and rebuild indexes for uploaded documents."""

    def reindex(self, document_id: str) -> dict:
        return {"document_id": document_id, "status": "indexing"}
