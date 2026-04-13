import re
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

    def _build_chunks(
        self,
        content: str,
        chunk_size: int = 360,
        min_chunk_size: int = 140,
    ) -> list[dict]:
        paragraphs = self._normalize_paragraphs(content)
        if not paragraphs:
            paragraphs = ["Document uploaded without extractable text."]

        chunks: list[dict] = []
        paragraph_offset = 0
        for paragraph_index, paragraph in enumerate(paragraphs):
            if len(paragraph) <= chunk_size:
                chunks.append(
                    {
                        "chunk_id": str(uuid4()),
                        "ordinal": len(chunks),
                        "snippet": paragraph[:160],
                        "content": paragraph,
                        "metadata_json": {
                            "start_offset": paragraph_offset,
                            "end_offset": paragraph_offset + len(paragraph),
                            "paragraph_index": paragraph_index,
                        },
                    }
                )
                paragraph_offset += len(paragraph) + 2
                continue

            units = self._split_paragraph_units(paragraph, max_unit_size=chunk_size)
            current_parts: list[str] = []
            current_start_offset = paragraph_offset
            current_end_offset = paragraph_offset

            for unit_text, unit_start, unit_end in units:
                addition_length = len(unit_text) if not current_parts else len(unit_text) + 1
                current_text = " ".join(current_parts)
                should_flush = (
                    bool(current_parts)
                    and (len(current_text) + addition_length) > chunk_size
                    and len(current_text) >= min_chunk_size
                )
                if should_flush:
                    chunk_text = current_text.strip()
                    chunks.append(
                        {
                            "chunk_id": str(uuid4()),
                            "ordinal": len(chunks),
                            "snippet": chunk_text[:160],
                            "content": chunk_text,
                            "metadata_json": {
                                "start_offset": current_start_offset,
                                "end_offset": current_end_offset,
                                "paragraph_index": paragraph_index,
                            },
                        }
                    )
                    current_parts = []

                if not current_parts:
                    current_start_offset = paragraph_offset + unit_start
                current_parts.append(unit_text)
                current_end_offset = paragraph_offset + unit_end

            if current_parts:
                chunk_text = " ".join(current_parts).strip()
                chunks.append(
                    {
                        "chunk_id": str(uuid4()),
                        "ordinal": len(chunks),
                        "snippet": chunk_text[:160],
                        "content": chunk_text,
                        "metadata_json": {
                            "start_offset": current_start_offset,
                            "end_offset": current_end_offset,
                            "paragraph_index": paragraph_index,
                        },
                    }
                )

            paragraph_offset += len(paragraph) + 2

        if not chunks:
            normalized = paragraphs[0]
            chunks.append(
                {
                    "chunk_id": str(uuid4()),
                    "ordinal": 0,
                    "snippet": normalized[:160],
                    "content": normalized,
                    "metadata_json": {"start_offset": 0, "end_offset": len(normalized), "paragraph_index": 0},
                }
            )
        return chunks

    def _normalize_paragraphs(self, content: str) -> list[str]:
        normalized = content.replace("\r\n", "\n").replace("\r", "\n")
        paragraphs: list[str] = []
        current_lines: list[str] = []
        for raw_line in normalized.split("\n"):
            line = " ".join(raw_line.split()).strip()
            if not line:
                if current_lines:
                    paragraphs.append("\n".join(current_lines).strip())
                    current_lines = []
                continue
            if self._starts_structured_block(line) and current_lines:
                paragraphs.append("\n".join(current_lines).strip())
                current_lines = []
            current_lines.append(line)
        if current_lines:
            paragraphs.append("\n".join(current_lines).strip())
        return paragraphs

    def _starts_structured_block(self, line: str) -> bool:
        stripped = line.strip()
        if not stripped:
            return False
        if re.match(r"^#{1,6}\s+", stripped):
            return True
        if re.match(r"^(?:q|question|问)\s*[:：]", stripped, flags=re.IGNORECASE):
            return True
        if re.match(r"^(?:\d+[.)、]|[-*•])\s+", stripped):
            return True
        if re.match(r"^【[^】]+】$", stripped):
            return True
        if stripped.endswith(("？", "?")):
            return True
        if len(stripped) <= 80 and any(token in stripped for token in ["如何", "怎么", "怎样", "怎么办", "哪里", "哪儿", "是否", "能否", "多久", "为什么", "是什么"]):
            return True
        return False

    def _split_paragraph_units(self, paragraph: str, *, max_unit_size: int) -> list[tuple[str, int, int]]:
        sentence_matches = list(re.finditer(r"[^。！？!?；;]+[。！？!?；;]?", paragraph))
        if not sentence_matches:
            return [(paragraph, 0, len(paragraph))]

        units: list[tuple[str, int, int]] = []
        for match in sentence_matches:
            raw_text = match.group(0)
            stripped = raw_text.strip()
            if not stripped:
                continue
            leading_ws = len(raw_text) - len(raw_text.lstrip())
            trailing_ws = len(raw_text) - len(raw_text.rstrip())
            start = match.start() + leading_ws
            end = match.end() - trailing_ws
            if len(stripped) <= max_unit_size:
                units.append((stripped, start, end))
                continue
            units.extend(self._split_long_unit(stripped, start_offset=start, max_unit_size=max_unit_size))
        return units or [(paragraph, 0, len(paragraph))]

    def _split_long_unit(self, text: str, *, start_offset: int, max_unit_size: int) -> list[tuple[str, int, int]]:
        secondary_matches = list(re.finditer(r"[^，,、：:]+[，,、：:]?", text))
        if len(secondary_matches) <= 1:
            return self._hard_split_unit(text, start_offset=start_offset, max_unit_size=max_unit_size)

        units: list[tuple[str, int, int]] = []
        for match in secondary_matches:
            raw_text = match.group(0)
            stripped = raw_text.strip()
            if not stripped:
                continue
            leading_ws = len(raw_text) - len(raw_text.lstrip())
            trailing_ws = len(raw_text) - len(raw_text.rstrip())
            start = start_offset + match.start() + leading_ws
            end = start_offset + match.end() - trailing_ws
            if len(stripped) <= max_unit_size:
                units.append((stripped, start, end))
                continue
            units.extend(self._hard_split_unit(stripped, start_offset=start, max_unit_size=max_unit_size))
        return units

    def _hard_split_unit(self, text: str, *, start_offset: int, max_unit_size: int) -> list[tuple[str, int, int]]:
        units: list[tuple[str, int, int]] = []
        start = 0
        while start < len(text):
            end = min(start + max_unit_size, len(text))
            chunk = text[start:end].strip()
            if chunk:
                leading_ws = len(text[start:end]) - len(text[start:end].lstrip())
                units.append((chunk, start_offset + start + leading_ws, start_offset + end))
            start = end
        return units

    def _report(self, progress_callback: Callable[[str, int], None] | None, status: str, progress_pct: int) -> None:
        if progress_callback is not None:
            progress_callback(status, progress_pct)
