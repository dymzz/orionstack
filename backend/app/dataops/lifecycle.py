"""Small retention contract; scheduling/deletion belongs to external operations."""
import os
from pydantic import Field
from app.knowledge.contracts import CoreContract


class RetentionPolicy(CoreContract):
    # None means undecided, not unlimited permission to keep data forever.
    source_days: int | None = Field(default=None,ge=1)
    derived_days: int | None = Field(default=None,ge=1)
    audit_days: int | None = Field(default=None,ge=1)
    telemetry_days: int | None = Field(default=None,ge=1)
    old_asset_version_days: int | None = Field(default=None,ge=1)
    raw_retrieval_days: int | None = Field(default=None,ge=1)
    deletion_execution: str = 'not_enabled'


def retention_policy():
    fields = ('source','derived','audit','telemetry','old_asset_version','raw_retrieval')
    return RetentionPolicy(**{f'{k}_days':os.getenv(f'ORIONSTACK_RETENTION_{k.upper()}_DAYS') or None for k in fields})
