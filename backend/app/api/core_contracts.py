"""Public document lifecycle responses for the PostgreSQL knowledge API."""

from typing import Literal
from pydantic import Field

from app.knowledge.contracts import CoreContract


class DocumentWriteResponse(CoreContract):
    document_id: str
    document_version: str
    status: Literal['pending', 'active']
    chunk_count: int | None = Field(default=None, ge=0)
    embedded_chunks: int | None = Field(default=None, ge=0)
    error_code: str | None = None


class DocumentListItem(CoreContract):
    document_id: str
    document_version: str
    filename: str
    status: Literal['pending', 'active']
    access_scope: str
    chunk_count: int = Field(ge=0)


class DocumentListResponse(CoreContract):
    items: tuple[DocumentListItem, ...]


class DocumentRevocationResponse(CoreContract):
    document_id: str
    status: Literal['revoked']


class CorePermissions(CoreContract):
    query: bool = True
    documents_read: bool = True
    documents_maintain: bool
    accounts_manage: bool = False
    backups_manage: bool = False
    audit_read: bool = False


class CoreAccessResponse(CoreContract):
    tenant_id: str
    user_id: str
    roles: tuple[str, ...]
    allowed_scopes: tuple[str, ...]
    permissions: CorePermissions
