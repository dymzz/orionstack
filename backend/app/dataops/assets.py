"""Versioned attachment metadata and mandatory quarantine, independent of RAG."""
import hashlib
from tempfile import SpooledTemporaryFile
from urllib.parse import quote
from uuid import uuid4
from psycopg.rows import dict_row
from app.dataops.contracts import AssetVersion, AttachmentTarget, UploadGrant
from app.dataops.adapters import S3ObjectStorage, TikaMediaDetector, ClamAVScanner
from app.dataops.ports import AssetRejected, DependencyUnavailable
from app.knowledge.postgres import PostgresDatabase
from app.security.cedar import dataops_authorizer


class AssetService:
    def __init__(self, database=None, storage=None, detector=None, scanner=None, authorizer=None):
        self.database = database or PostgresDatabase()
        self.storage = storage
        self.detector = detector
        self.scanner = scanner
        self.authorizer = authorizer or dataops_authorizer()

    def _storage(self): return self.storage or S3ObjectStorage()

    def _authorize(self, connection, access, action, kind, identity, owner=''):
        allowed = self.authorizer.allows(access, action, kind, identity, owner=owner)
        connection.execute('''INSERT INTO dataops.audit_events
            (tenant_id,id,principal_id,action,resource_type,resource_id,decision,policy_version)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)''',
            (access.tenant_id, uuid4().hex, access.user_id, action, kind, identity,
                'allow' if allowed else 'deny', self.authorizer.version))
        if not allowed: raise PermissionError('Cedar denied this operation')

    def _target(self, connection, access, target):
        if target.resource_type == 'collection':
            if target.resource_id != 'uploads': raise LookupError('Unknown attachment collection')
            return
        row = connection.execute('''SELECT 1 FROM core.documents d JOIN core.source_records s
            ON (d.tenant_id,d.source_record_id,d.source_version)=(s.tenant_id,s.source_record_id,s.source_version)
            WHERE d.tenant_id=%s AND d.document_id=%s AND d.lifecycle_status='active'
              AND s.lifecycle_status='active' AND d.access_scope=ANY(%s::text[])
              AND s.access_scope=ANY(%s::text[]) LIMIT 1''',
            (access.tenant_id, target.resource_id, list(access.allowed_scopes), list(access.allowed_scopes))).fetchone()
        if not row: raise LookupError('Attachment resource is unavailable')

    def _row(self, connection, version_id, access, *, lock=False):
        with connection.cursor(row_factory=dict_row) as cursor:
            row = cursor.execute('''SELECT v.*,a.kind,a.created_by AS owner,
                l.resource_type,l.resource_id,l.relation,o.object_key AS upload_key,
                r.object_key AS ready_key,r.provider_version_id
                FROM dataops.asset_versions v
                JOIN dataops.assets a USING (tenant_id,asset_id)
                JOIN dataops.attachment_links l USING (tenant_id,asset_id)
                JOIN dataops.storage_objects o ON (v.tenant_id,v.upload_object_id)=(o.tenant_id,o.object_id)
                LEFT JOIN dataops.storage_objects r ON (v.tenant_id,v.ready_object_id)=(r.tenant_id,r.object_id)
                WHERE v.tenant_id=%s AND v.asset_version_id=%s''' + (' FOR UPDATE OF v' if lock else ''),
                (access.tenant_id, version_id)).fetchone()
        if not row: raise LookupError('Asset version is unavailable')
        return row

    @staticmethod
    def _dto(row):
        return AssetVersion(**{k: row[k] for k in AssetVersion.model_fields if k != 'attachment'},
            attachment=AttachmentTarget(**{k: row[k] for k in ('resource_type','resource_id','relation')}))

    def begin_upload(self, request, access):
        with self.database.connection() as connection:
            self._target(connection, access, request.attachment)
            self._authorize(connection, access, 'AttachFile', 'Resource', request.attachment.resource_id)
            storage = self._storage()
            with connection.transaction():
                asset_id = request.asset_id or 'asset_' + uuid4().hex
                connection.execute('SELECT pg_advisory_xact_lock(hashtext(%s))', (access.tenant_id + ':asset:' + asset_id,))
                with connection.cursor(row_factory=dict_row) as cursor:
                    asset = cursor.execute('''SELECT a.*,l.resource_type,l.resource_id,l.relation
                        FROM dataops.assets a JOIN dataops.attachment_links l USING (tenant_id,asset_id)
                        WHERE a.tenant_id=%s AND a.asset_id=%s''', (access.tenant_id, asset_id)).fetchone()
                if request.asset_id and not asset: raise LookupError('Asset is unavailable')
                if asset:
                    target = request.attachment
                    if (asset['kind'] != request.kind or
                        (asset['resource_type'],asset['resource_id'],asset['relation']) !=
                        (target.resource_type,target.resource_id,target.relation)):
                        raise ValueError('Asset replacement must retain its business identity and attachment')
                else:
                    connection.execute('INSERT INTO dataops.assets (tenant_id,asset_id,kind,created_by) VALUES (%s,%s,%s,%s)',
                        (access.tenant_id,asset_id,request.kind,access.user_id))
                    target = request.attachment
                    connection.execute('INSERT INTO dataops.attachment_links VALUES (%s,%s,%s,%s,%s)',
                        (access.tenant_id,target.resource_type,target.resource_id,asset_id,target.relation))
                version = connection.execute('SELECT COALESCE(MAX(version),0)+1 FROM dataops.asset_versions WHERE tenant_id=%s AND asset_id=%s',
                    (access.tenant_id,asset_id)).fetchone()[0]
                version_id, object_id = 'av_' + uuid4().hex, 'obj_' + uuid4().hex
                key = f'tenant/{quote(access.tenant_id, safe="")}/assets/{asset_id}/{version_id}/quarantine'
                url, headers = storage.upload_url(key, request.size_bytes)
                connection.execute('INSERT INTO dataops.storage_objects (tenant_id,object_id,object_key) VALUES (%s,%s,%s)',
                    (access.tenant_id,object_id,key))
                connection.execute('''INSERT INTO dataops.asset_versions
                    (tenant_id,asset_version_id,asset_id,version,upload_object_id,expected_sha256,size_bytes,
                     media_type_hint,original_filename,relative_path,created_by,status)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'uploading')''',
                    (access.tenant_id,version_id,asset_id,version,object_id,request.expected_sha256,request.size_bytes,
                        request.media_type_hint,request.filename,request.relative_path,access.user_id))
                row = self._row(connection, version_id, access)
        return UploadGrant(version=self._dto(row), url=url, headers=headers)

    def finalize(self, version_id, access):
        # Commit quarantine before touching external scanners. Outages never return ready.
        with self.database.connection() as connection:
            row = self._row(connection, version_id, access)
            self._target(connection, access, AttachmentTarget(**{k:row[k] for k in ('resource_type','resource_id','relation')}))
            self._authorize(connection, access, 'FinalizeAsset','Asset',row['asset_id'],row['owner'])
            with connection.transaction():
                row = self._row(connection,version_id,access,lock=True)
                if row['status'] in ('ready','rejected'): return self._dto(row)
                if row['status'] == 'uploading':
                    connection.execute("UPDATE dataops.asset_versions SET status='quarantined' WHERE tenant_id=%s AND asset_version_id=%s",(access.tenant_id,version_id))
            with connection.transaction():
                row = self._row(connection,version_id,access,lock=True)
                if row['status'] in ('ready','rejected'): return self._dto(row)
                # Hold the version lock through synchronous inspection. A failed attempt
                # commits its own audit fact and returns to quarantine before retry.
                connection.execute("UPDATE dataops.asset_versions SET status='scanning' WHERE tenant_id=%s AND asset_version_id=%s",
                    (access.tenant_id,version_id))
                failure = None
                sha256, media_type, malware_clean, size = None, None, None, 0
                def inspect(outcome, reason=None):
                    connection.execute('''INSERT INTO dataops.asset_inspections
                        (tenant_id,inspection_id,asset_version_id,outcome,size_bytes,sha256,media_type,
                         malware_clean,reason_code,checked_by,policy_version)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
                        (access.tenant_id,uuid4().hex,version_id,outcome,size,sha256,media_type,
                         malware_clean,reason,access.user_id,self.authorizer.version))
                try:
                    storage = self._storage()
                    with SpooledTemporaryFile(max_size=8*1024*1024, mode='w+b') as verified:
                        digest, size = hashlib.sha256(), 0
                        with storage.open_upload(row['upload_key']) as data:
                            while block := data.read(1024*1024):
                                size += len(block)
                                if size > row['size_bytes']: raise AssetRejected('size_mismatch')
                                digest.update(block); verified.write(block)
                        sha256 = digest.hexdigest()
                        if size != row['size_bytes']: raise AssetRejected('size_mismatch')
                        if row['expected_sha256'] and row['expected_sha256'] != sha256: raise AssetRejected('sha256_mismatch')
                        detector = self.detector or TikaMediaDetector()
                        media_type = detector.detect(verified)
                        # Unknown binary types remain quarantined/rejected, not trusted by extension.
                        if media_type == 'application/octet-stream': raise AssetRejected('undetected_media_type')
                        scanner = self.scanner or ClamAVScanner()
                        malware_clean = scanner.scan(verified)
                        if not malware_clean: raise AssetRejected('malware_detected')
                        target = AttachmentTarget(**{k:row[k] for k in ('resource_type','resource_id','relation')})
                        self._target(connection, access, target)
                        self.authorizer.require(access,'FinalizeAsset','Asset',row['asset_id'],owner=row['owner'])
                        key = row['upload_key'].rsplit('/',1)[0] + '/verified-' + uuid4().hex
                        provider_version = storage.put_verified(key,verified,media_type,sha256)
                        object_id = 'obj_' + uuid4().hex
                        connection.execute('INSERT INTO dataops.storage_objects (tenant_id,object_id,object_key,provider_version_id) VALUES (%s,%s,%s,%s)',
                            (access.tenant_id,object_id,key,provider_version))
                        inspect('passed')
                        connection.execute("""UPDATE dataops.asset_versions SET status='ready',sha256=%s,media_type=%s,ready_object_id=%s
                            WHERE tenant_id=%s AND asset_version_id=%s""",(sha256,media_type,object_id,access.tenant_id,version_id))
                except AssetRejected as error:
                    inspect('rejected', str(error))
                    connection.execute("UPDATE dataops.asset_versions SET status='rejected',rejection_code=%s WHERE tenant_id=%s AND asset_version_id=%s",
                        (str(error),access.tenant_id,version_id))
                except DependencyUnavailable as error:
                    inspect('failed', 'dependency_unavailable')
                    connection.execute("UPDATE dataops.asset_versions SET status='quarantined' WHERE tenant_id=%s AND asset_version_id=%s",
                        (access.tenant_id,version_id))
                    failure = error
                result = self._dto(self._row(connection,version_id,access))
            if failure: raise failure
            return result

    def read(self, version_id, access):
        with self.database.connection() as connection:
            row = self._row(connection,version_id,access)
            self._authorize(connection,access,'ReadAsset','Asset',row['asset_id'],row['owner'])
            self._target(connection,access,AttachmentTarget(**{k:row[k] for k in ('resource_type','resource_id','relation')}))
        return self._dto(row)

    def download(self, version_id, access):
        with self.database.connection() as connection:
            row = self._row(connection,version_id,access)
            self._authorize(connection,access,'ReadAsset','Asset',row['asset_id'],row['owner'])
            self._target(connection,access,AttachmentTarget(**{k:row[k] for k in ('resource_type','resource_id','relation')}))
        if row['status'] != 'ready': raise PermissionError('Quarantined assets cannot be downloaded')
        return self._storage().download_url(row['ready_key'],row['original_filename'],row['provider_version_id'])
