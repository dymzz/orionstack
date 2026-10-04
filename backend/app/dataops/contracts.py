from datetime import datetime
from typing import Literal
from pathlib import PurePosixPath
from pydantic import Field, field_validator
from app.knowledge.contracts import CoreContract

AssetKind = Literal['file', 'drawing', 'invoice', 'site_photo', 'contract', 'supporting_document']
Relation = Literal['drawing', 'invoice', 'site_photo', 'supporting_document', 'contract', 'other']


class AttachmentTarget(CoreContract):
    resource_type: Literal['document', 'collection'] = 'collection'
    resource_id: str = Field(default='uploads', min_length=1, max_length=128)
    relation: Relation = 'other'


class UploadRequest(CoreContract):
    filename: str = Field(min_length=1, max_length=240)
    relative_path: str = Field(default='', max_length=1024)
    size_bytes: int = Field(gt=0, le=128 * 1024 * 1024)
    media_type_hint: str = Field(default='application/octet-stream', max_length=128)
    expected_sha256: str | None = Field(default=None, pattern=r'^[a-f0-9]{64}$')
    kind: AssetKind = 'file'
    asset_id: str | None = Field(default=None, pattern=r'^asset_[a-f0-9]{32}$')
    attachment: AttachmentTarget = Field(default_factory=AttachmentTarget)

    @field_validator('filename', 'relative_path')
    @classmethod
    def safe_path(cls, value):
        if not value: return value
        path = PurePosixPath(value)
        if ('\\' in value or ':' in value or path.is_absolute() or
                any(p in ('', '.', '..') for p in value.split('/')) or
                any(ord(c) < 32 for c in value)):
            raise ValueError('Invalid relative filename')
        return value

    @field_validator('filename')
    @classmethod
    def basename_only(cls, value):
        if '/' in value: raise ValueError('Filename must be a basename')
        return value


class AssetVersion(CoreContract):
    asset_id: str
    asset_version_id: str
    version: int
    kind: AssetKind
    tenant_id: str
    created_by: str
    created_at: datetime
    original_filename: str
    relative_path: str
    size_bytes: int
    sha256: str | None = None
    media_type: str | None = None
    status: Literal['uploading', 'quarantined', 'scanning', 'ready', 'rejected']
    rejection_code: str | None = None
    attachment: AttachmentTarget


class UploadGrant(CoreContract):
    version: AssetVersion
    method: Literal['PUT'] = 'PUT'
    url: str
    headers: dict[str, str]
    expires_in: int = 300


class DerivedArtifact(CoreContract):
    artifact_id: str
    asset_version_id: str
    kind: Literal['ocr_text', 'thumbnail', 'extracted_metadata', 'embedding_chunks']
    producer: str
    producer_version: str
    content_hash: str = Field(pattern=r'^[a-f0-9]{64}$')
    evidence_id: str | None = None
    created_at: datetime
