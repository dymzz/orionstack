from uuid import uuid4
from typing import Callable

from app.knowledge.embeddings.embedding_service import EmbeddingService
from app.models.entities import DocumentORM
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.embedding_repository import EmbeddingRepository
from app.repositories.pgvector_repository import PgVectorRepository


class IndexingStageError(RuntimeError):
    def __init__(self, *, stage: str, error_code: str, message: str) -> None:
        super().__init__(message)
        self.stage = stage
        self.error_code = error_code
        self.message = message


class IndexService:
    """Build and rebuild indexes for uploaded documents."""

    def __init__(self) -> None:
        self.repository = DocumentRepository()
        self.chunk_repository = ChunkRepository()
        self.embedding_repository = EmbeddingRepository()
        self.pgvector_repository = PgVectorRepository()
        self.embedding_service = EmbeddingService()

    def reindex(
        self,
        document_id: str,
        progress_callback: Callable[[str, int], None] | None = None,
    ) -> DocumentORM | None:
        document = self.repository.get(document_id)
        if document is None:
            return None

        self.repository.set_status(document_id, "indexing")
        self._report(progress_callback, "indexing", 5)
        try:
            chunks = self._build_chunks(document.content)
        except Exception as exc:
            raise IndexingStageError(
                stage="chunking",
                error_code="chunk_generation_failed",
                message="Failed while splitting document content into chunks.",
            ) from exc
        self._report(progress_callback, "chunking", 12)
        try:
            chunk_rows = self.chunk_repository.replace_for_document(document_id, chunks)
        except Exception as exc:
            raise IndexingStageError(
                stage="chunking",
                error_code="chunk_persist_failed",
                message="Failed while storing normalized chunks.",
            ) from exc
        self._report(progress_callback, "chunked", 22)

        vectors_by_chunk_id: dict[str, list[float]] = {}
        embedding_model = ""
        embedding_dim = 0
        batch_size = self.embedding_service.batch_size
        total_chunks = max(len(chunk_rows), 1)
        embedded_chunks = 0
        try:
            embedding_batches = self.embedding_service.embed_texts_in_batches(
                [chunk.content for chunk in chunk_rows],
                batch_size=batch_size,
            )
        except Exception as exc:
            raise IndexingStageError(
                stage="embedding",
                error_code="embedding_generation_failed",
                message="Failed while generating embedding vectors.",
            ) from exc

        for batch_index, batch in enumerate(embedding_batches, start=1):
            if not embedding_model:
                embedding_model = batch.model
                embedding_dim = batch.dimension

            start_index = (batch_index - 1) * batch_size
            end_index = min(start_index + len(batch.vectors), len(chunk_rows))
            current_chunk_rows = chunk_rows[start_index:end_index]
            for chunk, vector in zip(current_chunk_rows, batch.vectors, strict=False):
                vectors_by_chunk_id[chunk.chunk_id] = vector

            embedded_chunks += len(current_chunk_rows)
            embedding_progress = 22 + int((embedded_chunks / total_chunks) * 48)
            self._report(progress_callback, "embedding", embedding_progress)

        pgvector_enabled = self.pgvector_repository.is_enabled()
        self._report(progress_callback, "persisting", 78)
        try:
            embedding_rows = self.embedding_repository.replace_for_chunks(
                [chunk.chunk_id for chunk in chunk_rows],
                embedding_model=embedding_model,
                embedding_dim=embedding_dim,
                vectors_by_chunk_id=vectors_by_chunk_id,
                storage_backend="pgvector" if pgvector_enabled else "inline",
            )
        except Exception as exc:
            raise IndexingStageError(
                stage="persisting",
                error_code="embedding_persist_failed",
                message="Failed while storing embedding metadata.",
            ) from exc
        if pgvector_enabled:
            self._report(progress_callback, "syncing", 90)
            try:
                self.pgvector_repository.sync_embeddings(embedding_rows)
            except Exception as exc:
                raise IndexingStageError(
                    stage="syncing",
                    error_code="vector_sync_failed",
                    message="Failed while syncing vectors into pgvector storage.",
                ) from exc
        self._report(progress_callback, "storing", 95)

        # Keep the legacy JSON snapshot during the transition to normalized chunk tables.
        try:
            updated_document = self.repository.replace_chunks(document_id, chunks)
        except Exception as exc:
            raise IndexingStageError(
                stage="storing",
                error_code="document_snapshot_failed",
                message="Failed while updating the legacy document chunk snapshot.",
            ) from exc
        if updated_document is None:
            return None
        self.repository.set_status(document_id, "indexed")
        self._report(progress_callback, "indexed", 100)
        return self.repository.get(document_id)

    def _build_chunks(self, content: str, chunk_size: int = 280) -> list[dict]:
        normalized = " ".join(content.split())
        if not normalized:
            normalized = "Document uploaded without extractable text."

        chunks: list[dict] = []
        start = 0
        while start < len(normalized):
            chunk_text = normalized[start : start + chunk_size].strip()
            if chunk_text:
                chunks.append(
                    {
                        "chunk_id": str(uuid4()),
                        "ordinal": len(chunks),
                        "snippet": chunk_text[:160],
                        "content": chunk_text,
                        "metadata_json": {
                            "start_offset": start,
                            "end_offset": min(start + chunk_size, len(normalized)),
                        },
                    }
                )
            start += chunk_size

        if not chunks:
            chunks.append(
                {
                    "chunk_id": str(uuid4()),
                    "ordinal": 0,
                    "snippet": normalized[:160],
                    "content": normalized,
                    "metadata_json": {"start_offset": 0, "end_offset": len(normalized)},
                }
            )
        return chunks

    def _report(self, progress_callback: Callable[[str, int], None] | None, status: str, progress_pct: int) -> None:
        if progress_callback is not None:
            progress_callback(status, progress_pct)
