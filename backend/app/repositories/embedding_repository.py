from uuid import uuid4

from sqlalchemy import delete, select

from app.core.database import session_scope
from app.models.entities import ChunkEmbeddingORM


class EmbeddingRepository:
    def replace_for_chunks(
        self,
        chunk_ids: list[str],
        *,
        embedding_model: str,
        embedding_dim: int,
        vectors_by_chunk_id: dict[str, list[float]],
        storage_backend: str = "inline",
    ) -> list[ChunkEmbeddingORM]:
        if not chunk_ids:
            return []

        with session_scope() as db:
            db.execute(
                delete(ChunkEmbeddingORM).where(
                    ChunkEmbeddingORM.chunk_id.in_(chunk_ids),
                    ChunkEmbeddingORM.embedding_model == embedding_model,
                )
            )

            rows: list[ChunkEmbeddingORM] = []
            for chunk_id in chunk_ids:
                vector = vectors_by_chunk_id.get(chunk_id)
                embedding_id = str(uuid4())
                row = ChunkEmbeddingORM(
                    embedding_id=embedding_id,
                    chunk_id=chunk_id,
                    embedding_model=embedding_model,
                    embedding_dim=embedding_dim,
                    storage_backend=storage_backend,
                    storage_ref=embedding_id if storage_backend != "inline" else None,
                    vector_json=vector,
                )
                db.add(row)
                rows.append(row)

            db.flush()
            for row in rows:
                db.refresh(row)
            return rows

    def list_for_chunks(
        self,
        chunk_ids: list[str],
        *,
        embedding_model: str,
        storage_backend: str = "inline",
    ) -> list[ChunkEmbeddingORM]:
        if not chunk_ids:
            return []

        with session_scope() as db:
            stmt = (
                select(ChunkEmbeddingORM)
                .where(
                    ChunkEmbeddingORM.chunk_id.in_(chunk_ids),
                    ChunkEmbeddingORM.embedding_model == embedding_model,
                    ChunkEmbeddingORM.storage_backend == storage_backend,
                )
                .order_by(ChunkEmbeddingORM.created_at.desc())
            )
            return list(db.scalars(stmt))
