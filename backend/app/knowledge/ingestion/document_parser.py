from __future__ import annotations

from io import BytesIO
from pathlib import Path


class UnsupportedDocumentTypeError(ValueError):
    pass


class MissingParserDependencyError(RuntimeError):
    pass


class DocumentParser:
    """Parse uploaded files into normalized plain text."""

    TEXT_SUFFIXES = {".txt", ".md", ".markdown"}
    PDF_SUFFIXES = {".pdf"}
    DOCX_SUFFIXES = {".docx"}

    def parse(self, *, filename: str | None, content_type: str | None, payload: bytes) -> str:
        suffix = self._detect_suffix(filename=filename, content_type=content_type)
        if suffix in self.TEXT_SUFFIXES:
            return self._parse_text(payload)
        if suffix in self.PDF_SUFFIXES:
            return self._parse_pdf(payload)
        if suffix in self.DOCX_SUFFIXES:
            return self._parse_docx(payload)
        raise UnsupportedDocumentTypeError(
            f"Unsupported document type: {suffix or 'unknown'}. Supported types: txt, md, pdf, docx."
        )

    def _detect_suffix(self, *, filename: str | None, content_type: str | None) -> str:
        if filename:
            suffix = Path(filename).suffix.lower().strip()
            if suffix:
                return suffix

        content_type = (content_type or "").lower().strip()
        if content_type in {"text/plain", "text/markdown", "text/x-markdown"}:
            return ".txt"
        if content_type == "application/pdf":
            return ".pdf"
        if content_type in {
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }:
            return ".docx"
        return ""

    def _parse_text(self, payload: bytes) -> str:
        text = payload.decode("utf-8", errors="ignore")
        return self._normalize(text)

    def _parse_pdf(self, payload: bytes) -> str:
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise MissingParserDependencyError(
                "PDF parsing requires `pypdf`. Install project dependencies and retry."
            ) from exc

        reader = PdfReader(BytesIO(payload))
        pages = [(page.extract_text() or "").strip() for page in reader.pages]
        text = "\n\n".join(page for page in pages if page)
        return self._normalize(text)

    def _parse_docx(self, payload: bytes) -> str:
        try:
            from docx import Document
        except ImportError as exc:
            raise MissingParserDependencyError(
                "DOCX parsing requires `python-docx`. Install project dependencies and retry."
            ) from exc

        document = Document(BytesIO(payload))
        paragraphs = [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()]
        text = "\n".join(paragraphs)
        return self._normalize(text)

    def _normalize(self, text: str) -> str:
        normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
        if normalized:
            return normalized
        return "Document uploaded without extractable text."
