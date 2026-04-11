class RetrievalService:
    """Retrieve relevant chunks for a question."""

    def retrieve(self, question: str, document_ids: list[str] | None = None, top_k: int = 5) -> list[dict]:
        return []
