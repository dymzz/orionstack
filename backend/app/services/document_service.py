from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from app.services.chunk_service import ChunkService
from app.services.document_parser import DocumentParser
from app.schemas.document import DocumentUploadResponse
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
        parsed_text = self._parser.parse(filename=Path(filename).name, data=data).strip()
        if not parsed_text:
            raise ValueError("文档解析结果为空，暂无法建立最小文档链路")

        chunks = self._chunk_service.split(parsed_text)
        if not chunks:
            raise ValueError("文档切块结果为空，暂无法建立最小文档链路")

        record = self._repository.save(
            document_id=document_id,
            filename=Path(filename).name,
            content_type=file.content_type or "application/octet-stream",
            data=data,
        )
        relative_file_path = (Path("uploads") / Path(record["storage_path"]).name).as_posix()

        self._chunk_repository.save(
            document_id=document_id,
            filename=Path(filename).name,
            chunks=chunks,
            file_path=relative_file_path,
        )
        return DocumentUploadResponse(
            status="uploaded",
            text_length=len(parsed_text),
            chunk_count=len(chunks),
            **record,
        )
