"""Retired upload entry: explicit local migration compatibility only."""
import os
from fastapi import HTTPException


def require_legacy_upload():
    if (os.getenv('ORIONSTACK_APP_MODE','demo') in ('demo','dev') and
            os.getenv('ORIONSTACK_ENABLE_LEGACY_DOCUMENT_UPLOAD','false').lower() == 'true'):
        return
    raise HTTPException(410,'Legacy direct document upload is retired; use Assets quarantine upload')
