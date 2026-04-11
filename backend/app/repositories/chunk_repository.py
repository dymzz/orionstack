from sqlalchemy import delete, select

from app.core.database import session_scope
from app.models.entities import DocumentChunkORM


class ChunkRepository:
    def replace_for_document(self, document_id: str, chunks: list[dict]) -> list[DocumentChunkORM]:
        with session_scope() as db:
            db.execute(
                delete(DocumentChunkORM).where(DocumentChunkORM.document_id == document_id)
            )

            rows: list[DocumentChunkORM] = []
            for chunk in chunks:
                row = DocumentChunkORM(
                    chunk_id=str(chunk["chunk_id"]),
                    document_id=document_id,
                    ordinal=int(chunk["ordinal"]),
                    snippet=str(chunk.get("snippet", "")),
                    content=str(chunk.get("content", "")),
                    metadata_json=dict(chunk.get("metadata_json", {})),
                )
                db.add(row)
                rows.append(row)

            db.flush()
            for row in rows:
                db.refresh(row)
            return rows

    def list(self, document_ids: list[str] | None = None) -> list[DocumentChunkORM]:
        with session_scope() as db:
            stmt = select(DocumentChunkORM).order_by(
                DocumentChunkORM.document_id,
                DocumentChunkORM.ordinal,
            )
            if document_ids:
                stmt = stmt.where(DocumentChunkORM.document_id.in_(document_ids))
            return list(db.scalars(stmt))
