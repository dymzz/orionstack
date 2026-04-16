from io import BytesIO
from pathlib import Path

from docx import Document
from pypdf import PdfReader


class DocumentParser:
    def parse(self, *, filename: str, data: bytes) -> str:
        suffix = Path(filename).suffix.lower()
        if suffix in {".txt", ".md"}:
            return self._decode_text(data)
        if suffix == ".pdf":
            return self._parse_pdf(data)
        if suffix == ".docx":
            return self._parse_docx(data)
        raise ValueError("当前文件类型暂不支持解析")

    def _decode_text(self, data: bytes) -> str:
        for encoding in ("utf-8", "utf-8-sig", "gb18030"):
            try:
                return data.decode(encoding)
            except UnicodeDecodeError:
                continue
        raise ValueError("文本文件编码暂不支持解析")

    def _parse_pdf(self, data: bytes) -> str:
        try:
            reader = PdfReader(BytesIO(data))
            texts = [page.extract_text() or "" for page in reader.pages]
            return "\n\n".join(texts)
        except Exception as error:
            raise ValueError("PDF 解析失败") from error

    def _parse_docx(self, data: bytes) -> str:
        try:
            document = Document(BytesIO(data))
            paragraphs = [paragraph.text for paragraph in document.paragraphs if paragraph.text.strip()]
            return "\n\n".join(paragraphs)
        except Exception as error:
            raise ValueError("DOCX 解析失败") from error
