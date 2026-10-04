"""Allowlisted support bundle: versions and dependency state, never source text/secrets."""
import hashlib
import json
import os
from pathlib import Path
import tomllib
from app.dataops.lifecycle import retention_policy
from app.security.cedar import dataops_authorizer
from app.knowledge.postgres import PostgresDatabase


def dependency_configuration():
    return {'object_storage':bool(os.getenv('ORIONSTACK_S3_BUCKET')),
        'tika':bool(os.getenv('ORIONSTACK_TIKA_URL')), 'clamav':bool(os.getenv('ORIONSTACK_CLAMAV_HOST')),
        'pgbackrest':bool(os.getenv('ORIONSTACK_PGBACKREST_STANZA')),
        'tus':bool(os.getenv('ORIONSTACK_TUS_ENDPOINT'))}


def system_diagnostics(access, database=None):
    database = database or PostgresDatabase()
    state = {k:'configured_unchecked' if v else 'not_configured' for k,v in dependency_configuration().items()}
    state.update(postgresql='unknown',pgvector='unknown',oidc='not_configured',cedar='unknown',
        embedding='configured_unchecked',worker='not_configured',n8n='not_configured')
    migration, last_asset_ready, backlog, failed = None,None,None,None
    last_versions = {}
    try:
        with database.connection() as conn:
            pg = conn.execute("SELECT current_setting('server_version'),(SELECT extversion FROM pg_extension WHERE extname='vector')").fetchone()
            state['postgresql']='ok'; state['pgvector']='ok' if pg[1] else 'missing'
            migration = conn.execute('SELECT version FROM core.schema_migrations ORDER BY version DESC LIMIT 1').fetchone()[0]
            counters=conn.execute("""SELECT MAX(created_at) FILTER (WHERE status='ready'),
                COUNT(*) FILTER (WHERE status IN ('uploading','quarantined','scanning')),COUNT(*) FILTER (WHERE status='rejected')
                FROM dataops.asset_versions WHERE tenant_id=%s""",(access.tenant_id,)).fetchone()
            last_asset_ready,backlog,failed=counters
            latest = conn.execute("SELECT runtime_versions FROM retrieval.retrieval_event WHERE tenant_id=%s ORDER BY created_at DESC LIMIT 1", (access.tenant_id,)).fetchone()
            last_versions = latest[0] if latest else {}
    except Exception: state['postgresql']='unavailable'
    try: policy_version=dataops_authorizer().version; state['cedar']='ok'
    except Exception: policy_version=None; state['cedar']='unavailable'
    from app.account.settings import IdentitySettings
    identity=IdentitySettings()
    state['oidc']='demo_identity' if identity.mode=='demo' else ('configured_unchecked' if identity.issuer and identity.client_id else 'not_configured')
    if state['object_storage']=='configured_unchecked':
        try:
            from app.dataops.adapters import S3ObjectStorage
            storage=S3ObjectStorage(); storage.client.head_bucket(Bucket=storage.bucket); state['object_storage']='ok'
        except Exception: state['object_storage']='unavailable'
    root=Path(__file__).resolve().parents[3]
    version=tomllib.loads((root/'pyproject.toml').read_text(encoding='utf-8'))['project']['version']
    # Hash only these nonsecret behavior switches. Never hash passwords/tokens/URLs.
    configuration={key:os.getenv(key,'') for key in (
        'ORIONSTACK_EMBEDDING_PROVIDER','ORIONSTACK_EMBEDDING_MODEL','ORIONSTACK_QUERY_USE_JEV',
        'ORIONSTACK_AUTH_MODE','ORIONSTACK_CEDAR_POLICY_FILE')}
    configuration['retention']=retention_policy().model_dump()
    return {'schema_version':'1','versions':{'runtime_version':version,'policy_bundle_version':policy_version,
        'migration_version':migration, 'last_query_versions':last_versions},'service_health':state,
        'last_ingestion':None,'last_asset_ready':last_asset_ready,'queue_backlog':None,'failed_jobs':None,
        'pending_asset_versions':backlog,'rejected_asset_versions':failed,
        'recent_errors':{'rejected_asset_count':failed},
        'configuration_fingerprint':hashlib.sha256(json.dumps(configuration,sort_keys=True).encode()).hexdigest(),
        'retention':retention_policy().model_dump(),
        'recovery_domain':{'components':['postgresql','object_storage'],'restore_test':'not_run'},
        'contains_secrets':False,'contains_source_content':False}
