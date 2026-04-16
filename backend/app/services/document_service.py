from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from app.services.chunk_service import ChunkService
from app.services.document_parser import DocumentParser
from app.schemas.document import (
    DocumentDeleteResponse,
    DocumentListItem,
    DocumentListResponse,
    DocumentUploadResponse,
)
from app.storage.repositories.chunk_repo import ChunkRepository
from app.storage.repositories.document_repo import DocumentRepository


class DocumentService:
    _ALLOWED_SUFFIXES = {".txt", ".md", ".pdf", ".docx"}

    def __init__(self) -> None:
        self._repository = DocumentRepository()
        self._parser = DocumentParser()
        self._chunk_service = ChunkService()
        self._chunk_repository = ChunkRepository()

    async def register_upload(self, file: UploadFile) -> DocumentUploadResponse:
        filename = file.filename or "document"
        suffix = Path(filename).suffix.lower()
        if suffix not in self._ALLOWED_SUFFIXES:
            raise ValueError("当前仅支持 .txt / .md / .pdf / .docx 文件")

        data = await file.read()
        if not data:
            raise ValueError("上传文件不能为空")

        document_id = f"doc-{uuid4().hex[:12]}"
        parsed_text = self._parser.parse(
            filename=Path(filename).name, data=data
        ).strip()
        if not parsed_text:
            raise ValueError("文档解析结果为空，暂无法建立最小文档链路")

        chunks = self._chunk_service.split(parsed_text)
        if not chunks:
            raise ValueError("文档切块结果为空，暂无法建立最小文档链路")

        text_length = len(parsed_text)
        chunk_count = len(chunks)

        record = self._repository.save(
            document_id=document_id,
            filename=Path(filename).name,
            content_type=file.content_type or "application/octet-stream",
            data=data,
            text_length=text_length,
            chunk_count=chunk_count,
        )
        relative_file_path = (
            Path("uploads") / Path(record["storage_path"]).name
        ).as_posix()

        self._chunk_repository.save(
            document_id=document_id,
            filename=Path(filename).name,
            chunks=chunks,
            file_path=relative_file_path,
        )
        return DocumentUploadResponse(status="uploaded", **record)

    def list_documents(self) -> DocumentListResponse:
        documents = self._repository.list_all()
        chunk_records = self._chunk_repository.list_all()

        chunk_stats: dict[str, dict[str, int]] = {}
        for chunk in chunk_records:
            document_id = str(chunk.get("document_id", ""))
            if not document_id:
                continue
            stats = chunk_stats.setdefault(
                document_id, {"chunk_count": 0, "text_length": 0}
            )
            stats["chunk_count"] += 1
            stats["text_length"] += len(str(chunk.get("text", "")))

        items = [
            DocumentListItem(
                document_id=record["document_id"],
                filename=record["filename"],
                content_type=record["content_type"],
                size_bytes=record["size_bytes"],
                created_at=record["created_at"],
                text_length=int(
                    record.get(
                        "text_length",
                        chunk_stats.get(record["document_id"], {}).get(
                            "text_length", 0
                        ),
                    )
                ),
                chunk_count=int(
                    record.get(
                        "chunk_count",
                        chunk_stats.get(record["document_id"], {}).get(
                            "chunk_count", 0
                        ),
                    )
                ),
            )
            for record in sorted(
                documents,
                key=lambda item: str(item.get("created_at", "")),
                reverse=True,
            )
        ]
        return DocumentListResponse(items=items)

    def delete_document(self, document_id: str) -> DocumentDeleteResponse:
        deleted_record = self._repository.delete(document_id)
        if deleted_record is None:
            raise LookupError("document_not_found")

        self._chunk_repository.delete_by_document(document_id)
        return DocumentDeleteResponse(status="deleted", document_id=document_id)
