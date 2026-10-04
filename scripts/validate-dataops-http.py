"""Local BFF/DataOps acceptance; no external services or business-file uploads."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
import httpx
from app.account.settings import IdentitySettings
from app.config.settings import settings
from app.knowledge.contracts import AccessContext
from app.knowledge.postgres import PostgresDatabase
from app.retrieval.raw_journal import PostgresRawJournal


def validate():
    identity = IdentitySettings()
    if identity.mode != 'demo': raise RuntimeError('Local demo mode is required')
    accounts = settings.user_accounts
    admin = next(((name, password) for name, (password, role) in accounts.items() if role == 'admin'), None)
    reader = next(((name, password) for name, (password, role) in accounts.items() if role == 'user'), None)
    if not admin or not reader: raise RuntimeError('Configured demo identities are required')
    report = {'created_at':datetime.now(timezone.utc).isoformat(), 'checks':[]}
    def check(name, passed):
        if not passed: raise RuntimeError('Acceptance failed: ' + name)
        report['checks'].append(name)
    with httpx.Client(base_url='http://127.0.0.1:8000', timeout=180, trust_env=False) as client:
        def authenticate(account):
            login = client.post('/api/auth/demo-login', headers={'Origin':identity.public_origin},
                json={'username':account[0], 'password':account[1]})
            check('demo_login_' + ('admin' if account == admin else 'reader'), login.status_code == 200)
            check('opaque_http_only_session', 'HttpOnly' in login.headers.get('set-cookie',''))
            session = client.get('/api/auth/session')
            check('server_session_readable', session.status_code == 200)
            headers = {'Cookie':identity.cookie_name+'='+login.cookies[identity.cookie_name],
                'X-CSRF-Token':session.json()['csrf_token'], 'Origin':identity.public_origin}
            client.cookies.clear()
            return headers
        admin_headers, reader_headers = authenticate(admin), authenticate(reader)
        try:
            check('unauthenticated_dataops_denied', client.get('/api/dataops/config').status_code == 401)
            config = client.get('/api/dataops/config', headers=admin_headers)
            check('admin_configuration_available', config.status_code == 200)
            body = config.json()
            check('admin_cedar_upload_allowed', body['permissions']['assets_upload'])
            check('joint_recovery_domain', body['recovery_domain'] == ['postgresql','object_storage'])
            check('resumable_not_falsely_enabled', body['resumable_upload'] == 'not_enabled')
            reader_config = client.get('/api/dataops/config', headers=reader_headers).json()
            check('reader_has_no_privileged_dataops_permissions', not any(reader_config['permissions'].values()))
            upload = {'filename':'synthetic-validation.txt','size_bytes':8}
            check('reader_upload_denied_before_provider', client.post('/api/assets/uploads', headers=reader_headers, json=upload).status_code == 403)
            check('upload_requires_csrf', client.post('/api/assets/uploads', headers={k:v for k,v in admin_headers.items() if k!='X-CSRF-Token'}, json=upload).status_code == 403)
            check('upload_rejects_identity_from_json', client.post('/api/assets/uploads', headers=admin_headers, json={**upload,'tenant_id':'foreign','status':'ready'}).status_code == 422)
            if not body['dependencies']['object_storage']:
                check('unconfigured_storage_returns_unavailable', client.post('/api/assets/uploads', headers=admin_headers, json=upload).status_code == 503)
            check('unknown_asset_is_unavailable', client.get('/api/assets/versions/av_nonexistent', headers=admin_headers).status_code == 404)
            check('reader_backup_denied', client.get('/api/backups', headers=reader_headers).status_code == 403)
            if not body['dependencies']['pgbackrest']:
                check('unconfigured_backup_has_no_fabricated_success', client.get('/api/backups', headers=admin_headers).status_code == 503)
            check('reader_diagnostics_denied', client.get('/api/support/diagnostics', headers=reader_headers).status_code == 403)
            legacy = client.post('/api/documents', headers=admin_headers, files={'file':('synthetic.txt',b'test')})
            check('legacy_upload_cannot_bypass_quarantine', legacy.status_code == 410)
            access = AccessContext.model_validate({k:v for k,v in client.get('/api/access-context', headers=reader_headers).json().items() if k != 'permissions'})
            result = client.post('/api/query', headers=reader_headers,
                json={'query':'Fixed synthetic DataOps validation question.', 'document_ids':['dataops-validation-'+uuid4().hex]})
            check('new_core_query_works', result.status_code == 200)
            answer = result.json()
            check('absent_evidence_refuses_answer', answer['status'] == 'insufficient_evidence' and not answer['citations'] and answer['raw_candidate_count'] == 0)
            check('answer_and_evidence_keep_tenant', answer['tenant_id'] == access.tenant_id == answer['evidence_bundle']['tenant_id'])
            check('answer_versions_are_recorded', all(answer['runtime_versions'].get(k) for k in ('runtime_version','policy_bundle_version','retrieval_profile_version','model_revision','parser_version','prompt_version')))
            raw = PostgresRawJournal().load_raw(answer['retrieval_event_id'], access)
            check('raw_versions_survive_database_roundtrip', raw.event.runtime_versions.runtime_fingerprint == answer['runtime_versions']['runtime_fingerprint'])
            report['synthetic_retrieval_event_id'] = answer['retrieval_event_id']
            diagnostic = client.get('/api/support/diagnostics', headers=admin_headers, params={'export':True})
            check('diagnostics_is_downloadable', diagnostic.status_code == 200 and 'attachment' in diagnostic.headers.get('content-disposition',''))
            diagnostic_body = diagnostic.json()
            check('database_vector_cedar_checked', all(diagnostic_body['service_health'][name] == 'ok' for name in ('postgresql','pgvector','cedar')))
            check('migration_008_active', diagnostic_body['versions']['migration_version'] == '008_asset_inspection')
            check('unknown_worker_not_faked', diagnostic_body['queue_backlog'] is None and diagnostic_body['failed_jobs'] is None)
            check('restore_test_not_faked', diagnostic_body['recovery_domain']['restore_test'] == 'not_run')
            sensitive = [os.getenv(k,'') for k in ('ORIONSTACK_DATABASE_URL','DEEPSEEK_API_KEY','TYPESAFE_API_KEY','CF_API_TOKEN','ORIONSTACK_S3_SECRET_ACCESS_KEY','ORIONSTACK_OIDC_CLIENT_SECRET')]
            check('diagnostics_excludes_known_secrets_and_raw_query', all(s not in diagnostic.text for s in sensitive if len(s)>8) and 'Fixed synthetic DataOps validation question.' not in diagnostic.text)
            with PostgresDatabase().connection() as connection:
                row = connection.execute("SELECT COUNT(*) FROM dataops.audit_events WHERE tenant_id=%s AND principal_id=%s AND decision='deny'", (access.tenant_id,access.user_id)).fetchone()
                check('denied_requests_are_domain_audit_facts', row[0] > 0)
            report['migration_version'] = diagnostic_body['versions']['migration_version']
            report['service_health'] = diagnostic_body['service_health']
        finally:
            client.post('/api/auth/logout', headers=reader_headers)
            client.post('/api/auth/logout', headers=admin_headers)
    report['status'] = 'passed'
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--report', type=Path, default=ROOT/'.runtime/dataops/http-acceptance.json')
    args = parser.parse_args()
    if not args.live:
        print('Preview: local demo BFF, Cedar denial/configuration checks and one synthetic empty retrieval; --live executes')
    else:
        try: result = validate()
        except Exception as error:
            message = str(error) if isinstance(error,RuntimeError) and str(error).startswith('Acceptance failed: ') else type(error).__name__
            print('DataOps acceptance failed: '+message, file=sys.stderr)
            raise SystemExit(1) from None
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(f"DataOps HTTP acceptance passed: {len(result['checks'])} checks")
