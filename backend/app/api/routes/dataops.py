"""DataOps facade: upload metadata, quarantine, pgBackRest and safe diagnostics."""
from urllib.parse import quote
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse, StreamingResponse, JSONResponse
from app.api.core_access import require_core_access
from app.dataops.contracts import UploadRequest, UploadGrant, AssetVersion
from app.dataops.assets import AssetService
from app.dataops.backups import PgBackRest
from app.dataops.diagnostics import dependency_configuration, system_diagnostics
from app.dataops.ports import DependencyUnavailable
from app.knowledge.postgres import DatabaseUnavailable
from app.config.core_settings import CoreConfigurationError
from app.security.cedar import dataops_authorizer

router=APIRouter(prefix='/api',tags=['dataops'])
def get_asset_service():
    try: return AssetService()
    except DependencyUnavailable as error: raise failure(error) from None
def get_backups(): return PgBackRest()


def failure(error):
    if isinstance(error,PermissionError): return HTTPException(403,'Operation denied by current policy or quarantine')
    if isinstance(error,LookupError): return HTTPException(404,'Requested asset or backup is unavailable')
    if isinstance(error,ValueError): return HTTPException(400,'Invalid DataOps input')
    return HTTPException(503,'DataOps dependency is not configured or unavailable')


@router.get('/dataops/config')
def config(access=Depends(require_core_access)):
    try:
        auth=dataops_authorizer()
        return {'dependencies':dependency_configuration(),'permissions':{
            'assets_upload':auth.allows(access,'AttachFile','Resource','uploads'),
            'backups_read':auth.allows(access,'ListBackups','BackupRepository','cluster'),
            'backups_download':auth.allows(access,'DownloadBackup','BackupRepository','cluster'),
            'diagnostics_read':auth.allows(access,'SystemDiagnostics','System','diagnostics')},
            'policy_bundle_version':auth.version,'max_upload_bytes':128*1024*1024,
            'upload_protocol':'s3_presigned_put','resumable_upload':'not_enabled',
            'recovery_domain':['postgresql','object_storage']}
    except DependencyUnavailable as error: raise failure(error) from None


@router.post('/assets/uploads',response_model=UploadGrant)
def upload(payload:UploadRequest,access=Depends(require_core_access),service=Depends(get_asset_service)):
    try: return service.begin_upload(payload,access)
    except (PermissionError,LookupError,ValueError,DependencyUnavailable,DatabaseUnavailable,CoreConfigurationError) as error:
        raise failure(error) from None


@router.post('/assets/versions/{version_id}/finalize',response_model=AssetVersion)
def finalize(version_id:str,access=Depends(require_core_access),service=Depends(get_asset_service)):
    try: return service.finalize(version_id,access)
    except (PermissionError,LookupError,ValueError,DependencyUnavailable,DatabaseUnavailable,CoreConfigurationError) as error:
        raise failure(error) from None


@router.get('/assets/versions/{version_id}',response_model=AssetVersion)
def read(version_id:str,access=Depends(require_core_access),service=Depends(get_asset_service)):
    try: return service.read(version_id,access)
    except (PermissionError,LookupError,DependencyUnavailable,DatabaseUnavailable,CoreConfigurationError) as error:
        raise failure(error) from None


@router.get('/assets/versions/{version_id}/download')
def download(version_id:str,access=Depends(require_core_access),service=Depends(get_asset_service)):
    try: return RedirectResponse(service.download(version_id,access),status_code=303,
        headers={'Referrer-Policy':'no-referrer','Cache-Control':'no-store'})
    except (PermissionError,LookupError,DependencyUnavailable,DatabaseUnavailable,CoreConfigurationError) as error:
        raise failure(error) from None


def backup_permission(access,action):
    try:
        auth=dataops_authorizer(); allowed=auth.allows(access,action,'BackupRepository','cluster')
        from app.knowledge.postgres import PostgresDatabase
        with PostgresDatabase().connection() as connection:
            connection.execute('''INSERT INTO dataops.audit_events (tenant_id,id,principal_id,action,
                resource_type,resource_id,decision,policy_version) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)''',
                (access.tenant_id,uuid4().hex,access.user_id,action,'BackupRepository','cluster','allow' if allowed else 'deny',auth.version))
        if not allowed: raise PermissionError()
    except (PermissionError,DependencyUnavailable,DatabaseUnavailable,CoreConfigurationError) as error: raise failure(error) from None


@router.get('/backups')
def backups(access=Depends(require_core_access)):
    backup_permission(access,'ListBackups')
    try: return get_backups().info()
    except (DependencyUnavailable,ValueError) as error: raise failure(error) from None


@router.get('/backups/{backup_id}/files')
def files(backup_id:str,access=Depends(require_core_access)):
    backup_permission(access,'ListBackups')
    try: return {'items':get_backups().files(backup_id)}
    except (DependencyUnavailable,ValueError,LookupError) as error: raise failure(error) from None


@router.get('/backups/{backup_id}/download')
def backup_download(backup_id:str,filename:str,access=Depends(require_core_access)):
    backup_permission(access,'DownloadBackup')
    try:
        return StreamingResponse(get_backups().download(backup_id,filename),media_type='application/octet-stream',
            headers={'Content-Disposition':"attachment; filename*=UTF-8''"+quote(filename.rsplit('/',1)[-1],safe='')})
    except (DependencyUnavailable,ValueError,LookupError) as error: raise failure(error) from None


@router.get('/support/diagnostics')
def diagnostics(export:bool=False,access=Depends(require_core_access)):
    try:
        dataops_authorizer().require(access,'SystemDiagnostics','System','diagnostics')
        result=system_diagnostics(access)
        # Serialize timestamps with FastAPI's standard encoder for JSONResponse.
        from fastapi.encoders import jsonable_encoder
        return JSONResponse(jsonable_encoder(result),headers={
            'Content-Disposition':'attachment; filename="orionstack-diagnostics.json"'} if export else {})
    except (PermissionError,DependencyUnavailable,ValueError,CoreConfigurationError) as error: raise failure(error) from None
