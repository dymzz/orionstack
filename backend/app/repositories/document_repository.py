from sqlalchemy import select

from app.core.database import session_scope
from app.models.entities import DocumentORM


class DocumentRepository:
    def save(self, document: DocumentORM) -> DocumentORM:
        with session_scope() as db:
            db.add(document)
            db.flush()
            db.refresh(document)
        return document

    def list(
        self,
        document_ids: list[str] | None = None,
        *,
        owner_user_id: str | None = None,
    ) -> list[DocumentORM]:
        with session_scope() as db:
            stmt = select(DocumentORM).order_by(DocumentORM.created_at.desc())
            if document_ids:
                stmt = stmt.where(DocumentORM.document_id.in_(document_ids))
            if owner_user_id:
                stmt = stmt.where(DocumentORM.owner_user_id == owner_user_id)
            return list(db.scalars(stmt))

    def get(self, document_id: str, *, owner_user_id: str | None = None) -> DocumentORM | None:
        with session_scope() as db:
            stmt = select(DocumentORM).where(DocumentORM.document_id == document_id)
            if owner_user_id:
                stmt = stmt.where(DocumentORM.owner_user_id == owner_user_id)
            return db.scalar(stmt)

    def delete(self, document_id: str, *, owner_user_id: str | None = None) -> bool:
        with session_scope() as db:
            stmt = select(DocumentORM).where(DocumentORM.document_id == document_id)
            if owner_user_id:
                stmt = stmt.where(DocumentORM.owner_user_id == owner_user_id)
            document = db.scalar(stmt)
            if document is None:
                return False
            db.delete(document)
            return True

    def set_status(self, document_id: str, status: str) -> DocumentORM | None:
        with session_scope() as db:
            document = db.get(DocumentORM, document_id)
            if document is None:
                return None
            document.status = status
            db.flush()
            db.refresh(document)
            return document

    def replace_chunks(self, document_id: str, chunks: list[dict]) -> DocumentORM | None:
        with session_scope() as db:
            document = db.get(DocumentORM, document_id)
            if document is None:
                return None
            document.chunks_json = chunks
            db.flush()
            db.refresh(document)
            return document
