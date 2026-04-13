from __future__ import annotations

from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import session_scope, settings as database_settings
from app.models.entities import ChunkEmbeddingORM


class PgVectorRepository:
    def __init__(self) -> None:
        self.settings = get_settings()

    def is_enabled(self) -> bool:
        configured = (self.settings.vector_backend or "auto").lower()
        if configured == "inline":
            return False

        database_url = database_settings.database.dsn
        if not database_url.startswith("postgresql"):
            return False

        with session_scope() as db:
            exists = db.execute(
                text(
                    """
                    SELECT EXISTS (
                        SELECT 1
                        FROM information_schema.tables
                        WHERE table_name = 'pgvector_chunk_embeddings'
                    )
                    """
                )
            ).scalar_one()
        return bool(exists)

    def sync_embeddings(self, embeddings: list[ChunkEmbeddingORM]) -> None:
        if not embeddings or not self.is_enabled():
            return

        with session_scope() as db:
            for embedding in embeddings:
                vector_json = embedding.vector_json or []
                db.execute(
                    text(
                        """
                        INSERT INTO pgvector_chunk_embeddings (embedding_id, embedding)
                        VALUES (:embedding_id, CAST(:vector AS vector))
                        ON CONFLICT (embedding_id) DO UPDATE
                        SET embedding = EXCLUDED.embedding
                        """
                    ),
                    {
                        "embedding_id": embedding.embedding_id,
                        "vector": self._to_vector_literal(vector_json),
                    },
                )

    def search(
        self,
        *,
        query_vector: list[float],
        embedding_model: str,
        top_k: int,
        document_ids: list[str] | None = None,
    ) -> list[dict]:
        if not self.is_enabled():
            return []

        where_document = ""
        params: dict[str, object] = {
            "query_vector": self._to_vector_literal(query_vector),
            "embedding_model": embedding_model,
            "top_k": top_k,
        }
        if document_ids:
            where_document = "AND c.document_id = ANY(:document_ids)"
            params["document_ids"] = document_ids

        sql = f"""
            SELECT
                c.document_id AS document_id,
                d.name AS document_name,
                c.chunk_id AS chunk_id,
                c.snippet AS snippet,
                c.content AS content,
                1 - (p.embedding <=> CAST(:query_vector AS vector)) AS score
            FROM chunk_embeddings e
            JOIN document_chunks c ON c.chunk_id = e.chunk_id
            JOIN documents d ON d.document_id = c.document_id
            JOIN pgvector_chunk_embeddings p ON p.embedding_id = e.embedding_id
            WHERE e.embedding_model = :embedding_model
            {where_document}
            ORDER BY p.embedding <=> CAST(:query_vector AS vector)
            LIMIT :top_k
        """

        with session_scope() as db:
            rows = db.execute(text(sql), params).mappings().all()
        return [dict(row) for row in rows]

    def _to_vector_literal(self, vector: list[float]) -> str:
        return "[" + ",".join(f"{value:.12f}" for value in vector) + "]"
