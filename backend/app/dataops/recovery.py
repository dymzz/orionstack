"""A recovery domain includes database and object versions, plus restore-test facts."""
from datetime import datetime
from typing import Literal
from pydantic import Field, model_validator
from app.knowledge.contracts import CoreContract


class ObjectVersionState(CoreContract):
    asset_version_id: str
    object_key: str
    provider_version_id: str | None = None
    sha256: str = Field(pattern=r'^[a-f0-9]{64}$')


class RecoveryManifest(CoreContract):
    tenant_id: str
    backup_id: str
    database_backup_id: str
    object_storage_backup_id: str | None = None
    object_versions: tuple[ObjectVersionState,...] = ()
    created_at: datetime
    restore_test: Literal['not_run','passed','failed'] = 'not_run'
    restore_test_id: str | None = None
    restore_test_at: datetime | None = None
    references_verified: bool = False
    @model_validator(mode='after')
    def test_evidence(self):
        if self.restore_test != 'not_run' and (not self.restore_test_id or not self.restore_test_at):
            raise ValueError('Restore-test status requires a test record and timestamp')
        if self.references_verified and (not self.object_storage_backup_id or self.restore_test != 'passed'):
            raise ValueError('Recovery verification requires an object backup and a passed restore test')
        return self
