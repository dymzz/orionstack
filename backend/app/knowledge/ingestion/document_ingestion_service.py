class DocumentIngestionService:
    """Handle document upload registration and ingestion kickoff."""

    def register_upload(self, name: str, source_type: str = "upload") -> dict:
        return {"name": name, "source_type": source_type, "status": "uploaded"}
