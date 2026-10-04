"""Stable infrastructure ports, with no product-specific types in Core."""
from typing import BinaryIO, Protocol, ContextManager


class DependencyUnavailable(RuntimeError): pass
class AssetRejected(ValueError): pass


class ObjectStoragePort(Protocol):
    def upload_url(self, key: str, size: int) -> tuple[str, dict[str, str]]: ...
    def open_upload(self, key: str) -> ContextManager[BinaryIO]: ...
    def put_verified(self, key: str, data: BinaryIO, media_type: str, sha256: str) -> str | None: ...
    def download_url(self, key: str, filename: str, version_id: str | None) -> str: ...


class MediaDetectionPort(Protocol):
    def detect(self, data: BinaryIO) -> str: ...


class MalwareScanPort(Protocol):
    def scan(self, data: BinaryIO) -> bool: ...
