"""Assets must remain isolated and immutable even when upload and scanners fail."""
from contextlib import contextmanager
from io import BytesIO
import json
import subprocess
from datetime import datetime, timezone
import httpx
import pytest
from pydantic import ValidationError
from app.dataops.assets import AssetService
from app.dataops.contracts import UploadRequest
from app.dataops.adapters import TikaMediaDetector
from app.dataops.ports import DependencyUnavailable
from app.dataops.backups import PgBackRest
from app.dataops.recovery import RecoveryManifest
from app.dataops.diagnostics import system_diagnostics
from app.knowledge.contracts import AccessContext, content_hash
from app.security.cedar import CedarAuthorizer
from test_raw_postgres_integration import database, SqlFailure

ADMIN=AccessContext(tenant_id='tenant-a',user_id='admin',roles=('admin',))
READER=AccessContext(tenant_id='tenant-a',user_id='reader',roles=('user',))
FOREIGN=AccessContext(tenant_id='tenant-b',user_id='admin',roles=('admin',))

class Storage:
    def __init__(self): self.objects={}; self.downloads=[]
    def upload_url(self,key,size): self.last_key=key; return 'https://objects.invalid/upload', {'Content-Type':'application/octet-stream'}
    @contextmanager
    def open_upload(self,key): yield BytesIO(self.objects[key])
    def put_verified(self,key,data,media_type,sha256):
        data.seek(0); self.objects[key]=data.read(); return 's3-version-1'
    def download_url(self,key,name,version_id):
        self.downloads.append((key,name,version_id)); return 'https://objects.invalid/download'

class Detector:
    def __init__(self,media='application/pdf',fail=False): self.media=media; self.fail=fail; self.seen=None
    def detect(self,data):
        data.seek(0); self.seen=data.read()
        if self.fail: raise DependencyUnavailable('tika unavailable')
        return self.media

class Scanner:
    def __init__(self,clean=True,fail=False): self.clean=clean; self.fail=fail
    def scan(self,data):
        if self.fail: raise DependencyUnavailable('scanner unavailable')
        return self.clean

def fixture(database,*,media='application/pdf',clean=True,scan_fail=False):
    storage=Storage(); detector=Detector(media)
    service=AssetService(database,storage,detector,Scanner(clean,scan_fail),CedarAuthorizer())
    return service,storage,detector

def upload(service,storage,**kwargs):
    data=b'%PDF-1.7\noriginal bytes'
    request=UploadRequest(filename='invoice.pdf',size_bytes=len(data),expected_sha256=content_hash(data),**kwargs)
    grant=service.begin_upload(request,ADMIN)
    storage.objects[storage.last_key]=data
    return grant,data

def test_ready_requires_real_bytes_hash_detection_scan_and_keeps_original_version(database):
    service,storage,detector=fixture(database)
    grant,data=upload(service,storage)
    assert grant.version.status=='uploading'
    with pytest.raises(PermissionError): service.download(grant.version.asset_version_id,ADMIN)
    ready=service.finalize(grant.version.asset_version_id,ADMIN)
    assert ready.status=='ready' and ready.sha256==content_hash(data)
    assert detector.seen==data and ready.media_type=='application/pdf'
    assert ready.tenant_id==ADMIN.tenant_id
    first_key=storage.last_key
    assert first_key.startswith('tenant/tenant-a/assets/')
    service.download(ready.asset_version_id,ADMIN)
    ready_key=storage.downloads[-1][0]
    # URL still allows overwrite of quarantine only; verified download is an independent object.
    storage.objects[first_key]=b'changed after verification'
    assert storage.objects[ready_key]==data
    assert service.finalize(ready.asset_version_id,ADMIN)==ready
    second,_=upload(service,storage,asset_id=ready.asset_id)
    assert second.version.version==2 and second.version.asset_id==ready.asset_id
    assert service.read(ready.asset_version_id,ADMIN)==ready
    assert database.bridge.execute('SELECT count(*) FROM core.document_files').fetchone()[0]==0
    assert database.bridge.execute('SELECT count(*) FROM core.document_chunks').fetchone()[0]==0
    with pytest.raises(SqlFailure):
        with database.bridge.transaction():
            database.bridge.execute("UPDATE dataops.asset_versions SET sha256=%s WHERE tenant_id=%s AND asset_version_id=%s",('0'*64,ADMIN.tenant_id,ready.asset_version_id))

@pytest.mark.parametrize('mode,code',[
    ('size','size_mismatch'),('hash','sha256_mismatch'),
    ('unknown_type','undetected_media_type'),('malware','malware_detected'),
])
def test_failed_validation_never_promotes_or_downloads(database,mode,code):
    service,storage,_=fixture(database,media='application/octet-stream' if mode=='unknown_type' else 'application/pdf',clean=mode!='malware')
    grant,data=upload(service,storage)
    if mode=='size': storage.objects[storage.last_key]=data+b'extra'
    if mode=='hash': storage.objects[storage.last_key]=b'x'*len(data)
    result=service.finalize(grant.version.asset_version_id,ADMIN)
    assert result.status=='rejected' and result.rejection_code==code
    with pytest.raises(PermissionError): service.download(result.asset_version_id,ADMIN)
    assert len(storage.objects)==1

def test_scanner_outage_commits_quarantine_and_retry_cannot_skip_it(database):
    service,storage,_=fixture(database,scan_fail=True)
    grant,_=upload(service,storage)
    with pytest.raises(DependencyUnavailable): service.finalize(grant.version.asset_version_id,ADMIN)
    assert service.read(grant.version.asset_version_id,ADMIN).status=='quarantined'
    inspections=database.bridge.execute('SELECT outcome,reason_code FROM dataops.asset_inspections ORDER BY created_at').fetchall()
    assert inspections==[('failed','dependency_unavailable')]
    service.scanner=Scanner()
    assert service.finalize(grant.version.asset_version_id,ADMIN).status=='ready'
    assert database.bridge.execute("SELECT count(*) FROM dataops.asset_inspections WHERE outcome='passed'").fetchone()[0]==1


def test_database_blocks_scan_bypass_and_unready_derived_artifacts(database):
    service,storage,_=fixture(database)
    grant,data=upload(service,storage)
    version_id=grant.version.asset_version_id
    def derive():
        database.bridge.execute('''INSERT INTO dataops.derived_artifacts
            (tenant_id,artifact_id,asset_version_id,kind,producer,producer_version,content_hash)
            VALUES (%s,'ocr-test',%s,'ocr_text','test-worker','1',%s)''',
            (ADMIN.tenant_id,version_id,content_hash(data)))
    with pytest.raises(SqlFailure):
        with database.bridge.transaction(): derive()
    with pytest.raises(SqlFailure):
        with database.bridge.transaction():
            database.bridge.execute("UPDATE dataops.asset_versions SET status='ready',sha256=%s,media_type='application/pdf',ready_object_id=upload_object_id WHERE asset_version_id=%s",
                (content_hash(data),version_id))
    with pytest.raises(SqlFailure):
        with database.bridge.transaction():
            database.bridge.execute("UPDATE dataops.asset_versions SET status='quarantined' WHERE asset_version_id=%s",(version_id,))
            database.bridge.execute("UPDATE dataops.asset_versions SET status='scanning' WHERE asset_version_id=%s",(version_id,))
            database.bridge.execute("UPDATE dataops.asset_versions SET status='ready',sha256=%s,media_type='application/pdf',ready_object_id=upload_object_id WHERE asset_version_id=%s",
                (content_hash(data),version_id))
    ready=service.finalize(version_id,ADMIN)
    assert ready.status=='ready'
    with database.bridge.transaction(): derive()
    inspection=database.bridge.execute('SELECT outcome,sha256,malware_clean FROM dataops.asset_inspections').fetchone()
    assert inspection==('passed',content_hash(data),True)
    with pytest.raises(SqlFailure):
        with database.bridge.transaction(): database.bridge.execute("DELETE FROM dataops.asset_inspections")


def test_database_rejected_is_terminal_and_initial_state_cannot_be_forged(database):
    service,storage,_=fixture(database,clean=False)
    grant,_=upload(service,storage)
    rejected=service.finalize(grant.version.asset_version_id,ADMIN)
    assert rejected.status=='rejected'
    assert service.finalize(rejected.asset_version_id,ADMIN)==rejected
    assert database.bridge.execute('SELECT outcome,reason_code FROM dataops.asset_inspections').fetchall()==[('rejected','malware_detected')]
    with pytest.raises(SqlFailure):
        with database.bridge.transaction():
            database.bridge.execute("UPDATE dataops.asset_versions SET status='ready' WHERE asset_version_id=%s",(rejected.asset_version_id,))
    with pytest.raises(SqlFailure):
        with database.bridge.transaction():
            database.bridge.execute('''INSERT INTO dataops.asset_versions
                SELECT tenant_id,'forged',asset_id,2,upload_object_id,NULL,expected_sha256,NULL,size_bytes,
                    media_type_hint,NULL,original_filename,relative_path,created_by,created_at,'quarantined',NULL
                FROM dataops.asset_versions WHERE asset_version_id=%s''',(rejected.asset_version_id,))

def test_tenant_and_owner_checks_precede_object_reads_and_downloads(database):
    service,storage,_=fixture(database)
    grant,_=upload(service,storage)
    with pytest.raises(LookupError): service.read(grant.version.asset_version_id,FOREIGN)
    with pytest.raises(PermissionError): service.read(grant.version.asset_version_id,READER)
    with pytest.raises(PermissionError): service.begin_upload(UploadRequest(filename='x.txt',size_bytes=1),READER)
    assert not storage.downloads
    audit=database.bridge.execute("SELECT decision FROM dataops.audit_events WHERE principal_id='reader'").fetchall()
    assert audit and all(row[0]=='deny' for row in audit)
    with pytest.raises(SqlFailure):
        with database.bridge.transaction():
            database.bridge.execute("INSERT INTO dataops.attachment_links VALUES ('tenant-b','collection','uploads',%s,'other')",(grant.version.asset_id,))

@pytest.mark.parametrize('field,value',[
    ('filename','../secret.pdf'),('relative_path','folder/../file.pdf'),
    ('relative_path','C:\\secret.pdf'),('relative_path','/etc/passwd'),
    ('tenant_id','tenant-b'),('status','ready'),('created_by','admin'),('authorized',True),
])
def test_upload_cannot_choose_identity_paths_or_trust_state(field,value):
    with pytest.raises(ValidationError):
        UploadRequest.model_validate({'filename':'safe.pdf','size_bytes':10,field:value})

def test_cedar_never_grants_cross_tenant_or_tenant_admin_cluster_backups(monkeypatch):
    monkeypatch.setenv('ORIONSTACK_AUTH_MODE','oidc')
    monkeypatch.setenv('ORIONSTACK_BACKUP_OPERATORS','tenant-a:admin')
    auth=CedarAuthorizer()
    assert auth.allows(ADMIN,'AttachFile','Resource','uploads')
    assert not auth.allows(FOREIGN,'AttachFile','Resource','uploads',tenant_id='tenant-a')
    assert auth.allows(ADMIN,'ListBackups','BackupRepository','cluster')
    assert not auth.allows(FOREIGN,'ListBackups','BackupRepository','cluster')
    assert not auth.allows(READER,'ListBackups','BackupRepository','cluster')
    with pytest.raises(DependencyUnavailable): CedarAuthorizer('this is not a policy')

def test_tika_uses_actual_stream_without_filename_or_browser_hint():
    captured={}
    def response(request):
        captured['body']=request.read(); captured['headers']=request.headers
        assert request.url.path=='/detect/stream'
        return httpx.Response(200,text='application/pdf')
    detector=TikaMediaDetector('http://tika.invalid',httpx.Client(transport=httpx.MockTransport(response)))
    assert detector.detect(BytesIO(b'%PDF-1.7'))=='application/pdf'
    assert captured['body']==b'%PDF-1.7' and 'content-disposition' not in captured['headers']

def test_pgbackrest_catalog_is_structured_and_download_names_whitelisted():
    calls=[]
    label='20261003-010000F'
    def runner(command,**kwargs):
        calls.append(command)
        if 'info' in command:
            data=[{'name':'orion','status':{'message':'ok'},'backup':[{'label':label,'type':'full','timestamp':{'stop':1}}]}]
        else:
            data={'backup.manifest':{'type':'file','size':100},'../config':{'type':'file'},'base/link':{'type':'link'}}
        return subprocess.CompletedProcess(command,0,json.dumps(data).encode(),b'')
    provider=PgBackRest(executable='pgbackrest',stanza='orion',runner=runner)
    assert provider.info()['items'][0]['restore_test']=='not_run'
    assert provider.files(label)==[{'filename':'backup.manifest','size_bytes':100}]
    with pytest.raises(ValueError): provider.files('--config=attacker')
    with pytest.raises(LookupError): provider.download(label,'../config')
    assert all(isinstance(c,list) for c in calls) and all('--repo=1' in c for c in calls)

def test_diagnostics_redacts_secret_and_original_content(database,monkeypatch):
    monkeypatch.setenv('DEEPSEEK_API_KEY','never-export-this-secret')
    monkeypatch.setenv('ORIONSTACK_S3_BUCKET','')
    result=system_diagnostics(ADMIN,database)
    serialized=json.dumps(result,default=str)
    assert 'never-export-this-secret' not in serialized and 'DEEPSEEK_API_KEY' not in serialized
    assert result['service_health']['postgresql']=='ok'
    assert result['service_health']['object_storage']=='not_configured'
    assert result['retention']['source_days'] is None
    assert result['recovery_domain']['restore_test']=='not_run'

def test_recovery_claim_requires_both_components_and_actual_test_record():
    with pytest.raises(ValidationError):
        RecoveryManifest(tenant_id='tenant-a',backup_id='backup1',database_backup_id='db1',
            created_at=datetime.now(timezone.utc),references_verified=True)
    with pytest.raises(ValidationError):
        RecoveryManifest(tenant_id='tenant-a',backup_id='backup1',database_backup_id='db1',
            created_at=datetime.now(timezone.utc),restore_test='passed')


def test_legacy_upload_is_retired_by_default_and_always_in_production(monkeypatch):
    from app.dataops.legacy import require_legacy_upload
    from fastapi import HTTPException
    monkeypatch.delenv('ORIONSTACK_ENABLE_LEGACY_DOCUMENT_UPLOAD', raising=False)
    monkeypatch.setenv('ORIONSTACK_APP_MODE','demo')
    with pytest.raises(HTTPException) as retired: require_legacy_upload()
    assert retired.value.status_code == 410
    monkeypatch.setenv('ORIONSTACK_ENABLE_LEGACY_DOCUMENT_UPLOAD','true')
    require_legacy_upload()
    monkeypatch.setenv('ORIONSTACK_APP_MODE','prod')
    with pytest.raises(HTTPException): require_legacy_upload()
