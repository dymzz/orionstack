"""26 frozen local acceptance cases. Preview by default; --live calls real DeepSeek."""
import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from app.evaluation.semantic_acceptance import digest, normalized, validate_suite, score_knowledge, summarize


def regrade(args, suite, fingerprint):
    """Correct derived scoring from immutable stored runs; never repeat a model call."""
    from app.config.core_settings import CoreSettings
    from app.account.settings import IdentitySettings
    from app.knowledge.postgres import PostgresDatabase
    from app.workbench.audit import RunAuditRepository
    original = json.loads(args.regrade.read_text(encoding='utf-8'))
    if original['suite_hash'] != fingerprint or len(original['results']) != len(suite['cases']):
        raise ValueError('Regrading needs a complete run of this exact frozen suite')
    settings = CoreSettings()
    if IdentitySettings().validate().mode != 'demo':
        raise ValueError('Regrading is restricted to explicit local demo acceptance')
    access = settings.access_for_user('test', 'user')
    if access.tenant_id != suite['tenant_id']:
        raise ValueError('Regrading requires the same server-owned validation principal')
    output = (args.report or args.regrade.with_name(args.regrade.stem+'-regraded.json')).resolve()
    if not output.is_relative_to(ROOT/'.runtime') or output.exists():
        raise ValueError('Regrading writes a new workspace report, preserving the original')
    database = PostgresDatabase()
    repository = RunAuditRepository(database)
    with database.connection() as connection:
        count_before = connection.execute('SELECT count(*) FROM qa.workbench_runs WHERE tenant_id=%s AND user_id=%s',
            (access.tenant_id,access.user_id)).fetchone()[0]
    for row in original['results']:
        if row['category'] not in ('positive','unanswerable'):
            continue
        case = next(case for case in suite['cases'] if case['id']==row['id'])
        audit = repository.read(row['request_id'],access).model_dump(mode='json')
        with database.connection() as connection:
            stored = connection.execute('SELECT response FROM qa.workbench_runs WHERE tenant_id=%s AND user_id=%s AND id=%s',
                (access.tenant_id,access.user_id,row['request_id'])).fetchone()[0]
        if (stored['execution_feedback'] != row['execution_feedback']
                or digest(audit['raw']) != row['raw_fingerprint']):
            raise ValueError('Stored original response or raw snapshot differs from the first run')
        row['original_scoring'] = {key:row.get(key) for key in ('passed','failure_stage','raw_gold','final_gold')}
        row.update(score_knowledge(case,row['http_status'],stored,audit,suite))
        row['final_candidate_ids'] = next((p['selected_candidate_ids'] for p in audit['processing']
            if p['id']==row['processing_run_id']),[])
    with database.connection() as connection:
        count_after = connection.execute('SELECT count(*) FROM qa.workbench_runs WHERE tenant_id=%s AND user_id=%s',
            (access.tenant_id,access.user_id)).fetchone()[0]
    if count_before != count_after:
        raise ValueError('Concurrent owner runs prevent a no-new-model-run assertion')
    original.update(summarize(original['results'],suite['gates']))
    original.update(regrade_parent=str(args.regrade.resolve().relative_to(ROOT)),new_model_requests=0,
        regraded_at=datetime.now(timezone.utc).isoformat(),scorer_fingerprint=digest(
            (ROOT/'backend/app/evaluation/semantic_acceptance.py').read_text(encoding='utf-8')))
    original['status'] = 'passed' if original['gates_passed'] else 'completed_with_quality_failures'
    original['failed_case_ids'] = [row['id'] for row in original['results'] if not row['passed']]
    output.write_text(json.dumps(original,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    output.with_name(output.stem+'-failures.json').write_text(json.dumps(
        {'suite_hash':fingerprint,'regrade_parent':original['regrade_parent'],
         'cases':[row for row in original['results'] if not row['passed']]},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':original['status'],'metrics':original['metrics'],
        'failed_cases':original['failed_case_ids'],'new_model_requests':0,'report':str(output)}))
    return 0 if original['gates_passed'] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--suite', type=Path, default=ROOT / 'evals/workbench-smoke-26-v1.json')
    parser.add_argument('--source-root', type=Path, default=ROOT / '.runtime/benchmarks/workbench-validation/source')
    parser.add_argument('--report', type=Path)
    parser.add_argument('--regrade', type=Path, help='Re-read actual stored runs and rescore without model requests')
    args = parser.parse_args()
    suite = json.loads(args.suite.read_text(encoding='utf-8'))
    fingerprint = validate_suite(suite, args.source_root)
    if args.regrade:
        if args.live:
            raise ValueError('Regrading and live model execution are separate operations')
        return regrade(args, suite, fingerprint)
    if not args.live:
        print(json.dumps({'mode': 'preview_no_http_no_model_no_database_write', 'case_count': len(suite['cases']),
            'suite_id': suite['suite_id'], 'suite_hash': fingerprint, 'gates': suite['gates']}))
        return 0
    import httpx
    from app.config.settings import settings
    from app.config.core_settings import CoreSettings
    from app.account.settings import IdentitySettings
    from app.knowledge.postgres import PostgresDatabase, SchemaMigrator
    identity = IdentitySettings().validate()
    config = CoreSettings()
    if (identity.mode != 'demo' or config.embedding_provider != 'onnx'
            or any(config.access_for_user(name, role).tenant_id != suite['tenant_id']
                   for name, role in (('test', 'user'), ('admin', 'admin')))):
        raise ValueError('Live smoke acceptance needs explicit local demo bindings and ONNX')
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid4().hex[:8]
    output = (args.report or ROOT / '.runtime/workbench/semantic' / (run_id + '.json')).resolve()
    if not output.is_relative_to(ROOT / '.runtime') or output.exists():
        raise ValueError('Use a new report path within this workspace .runtime')
    output.parent.mkdir(parents=True, exist_ok=True)
    report = {'run_id': run_id, 'started_at': datetime.now(timezone.utc).isoformat(), 'status': 'running',
        'transport': 'real_vite_proxy_bff_postgresql_onnx_deepseek', 'suite_hash': fingerprint,
        'suite': suite, 'automatic_retries': False, 'results': [], 'versions': [],
        'scorer_fingerprint':digest((ROOT/'backend/app/evaluation/semantic_acceptance.py').read_text(encoding='utf-8'))}
    db = PostgresDatabase()
    def save():
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    def run_count():
        with db.connection() as connection:
            return connection.execute('SELECT count(*) FROM qa.workbench_runs WHERE tenant_id=%s AND user_id=%s',
                (suite['tenant_id'], 'test')).fetchone()[0]
    def login(client, name):
        response = client.post('/api/auth/demo-login', headers={'Origin': identity.public_origin},
            json={'username': name, 'password': settings.user_accounts[name][0]})
        if response.status_code != 200:
            raise ValueError('Configured demo authentication failed')
        session = client.get('/api/auth/session').json()
        return {'Origin': identity.public_origin, 'X-CSRF-Token': session['csrf_token']}
    save()
    responses = {}
    with httpx.Client(base_url='http://127.0.0.1:5173', timeout=180, trust_env=False) as client:
        headers = login(client, 'test')
        try:
            access = client.get('/api/access-context').json()
            if access['user_id'] != 'test' or access['roles'] != ['user'] or access['tenant_id'] != suite['tenant_id']:
                raise ValueError('Unexpected server principal')
            listing = client.get('/api/documents').json()['items']
            if len(listing) != len(suite['sources']) or any(not any(
                    row['document_id'] == pin['document_id'] and row['document_version'] == pin['document_version']
                    for row in listing) for pin in suite['sources']):
                raise ValueError('Authorized active source snapshot differs from the frozen suite')
            with db.connection() as connection:
                installed = dict(connection.execute('SELECT version,checksum FROM core.schema_migrations').fetchall())
                if any(installed.get(m.version) != m.checksum for m in SchemaMigrator().migrations()):
                    raise ValueError('Installed schema differs from local immutable migrations')
                report['migration_version'] = connection.execute('SELECT version_num FROM core.alembic_version').fetchone()[0]
            for case in suite['cases']:
                started = time.monotonic()
                row = {'id': case['id'], 'category': case['category'], 'query': case['query'], 'passed': False}
                try:
                    audit = None
                    if case['category'] in ('positive', 'unanswerable'):
                        response = client.post('/api/query', headers=headers,
                            json={'query': case['query'], 'top_k': suite['top_k'], 'final_top_k': suite['final_top_k']})
                        data = response.json()
                        receipt = data.get('execution_feedback') or {}
                        request_id = receipt.get('request_id')
                        if request_id:
                            readback = client.get('/api/query-runs/' + request_id)
                            if readback.status_code == 200:
                                audit = readback.json()
                        row.update(score_knowledge(case, response.status_code, data, audit, suite))
                    elif case['category'] == 'chat':
                        payload = {'query': case['query']}
                        if case['scenario'] == 'chat_followup':
                            first_case = next(c for c in suite['cases'] if c['id'] == 'C01')
                            payload['messages'] = [{'role': 'user', 'content': first_case['query']},
                                {'role': 'assistant', 'content': responses['C01']['answer']}]
                        response = client.post('/api/chat', headers=headers, json=payload)
                        data = response.json()
                        receipt = data.get('execution_feedback') or {}
                        request_id = receipt.get('request_id')
                        readback = client.get('/api/query-runs/' + request_id) if request_id else None
                        audit = readback.json() if readback is not None and readback.status_code == 200 else None
                        checks = {'http_200': response.status_code == 200,
                            'expected_chat_facts': all(normalized(term) in normalized(data.get('answer', '')) for term in case['answer_terms']),
                            'ordinary_unverified_label': data.get('validation') == 'unverified_general_response',
                            'no_retrieval_claims': all(receipt.get(key) is None for key in ('retrieval_event_id', 'processing_run_id', 'raw_candidate_count')),
                            'no_citations_or_evidence': 'citations' not in data and 'evidence_bundle' not in data,
                            'actual_provider_succeeded': receipt.get('model_call', {}).get('attempted') is True and receipt.get('model_call', {}).get('status') == 'succeeded',
                            'own_independent_audit': bool(audit and audit['run']['actor_user_id'] == 'test' and audit['raw'] is None and not audit['processing'])}
                        row.update(checks=checks, passed=all(checks.values()))
                    elif case['category'] == 'boundary':
                        scenario = case['scenario']
                        count_before = run_count()
                        if scenario == 'anonymous_query':
                            with httpx.Client(base_url='http://127.0.0.1:5173', timeout=30, trust_env=False) as anon:
                                response = anon.post('/api/query', json={'query': case['query']})
                            checks = {'anonymous_401': response.status_code == 401}
                        elif scenario == 'missing_csrf':
                            response = client.post('/api/query', headers={'Origin': identity.public_origin}, json={'query': case['query']})
                            checks = {'missing_csrf_403': response.status_code == 403}
                        elif scenario == 'forged_tenant':
                            response = client.post('/api/query', headers=headers, json={'query': case['query'], 'tenant_id': 'foreign-tenant'})
                            checks = {'forged_tenant_422': response.status_code == 422}
                        elif scenario == 'out_of_scope_identity_text':
                            response = client.post('/api/query', headers=headers, json={'query': case['query'],
                                'document_ids': ['erag-confluence:dsid_014c42df40884fed9420bb55fc665a76']})
                            data = response.json()
                            receipt = data.get('execution_feedback') or {}
                            with db.connection() as connection:
                                stored = connection.execute('SELECT access_snapshot FROM qa.workbench_runs WHERE tenant_id=%s AND id=%s',
                                    (suite['tenant_id'], receipt.get('request_id'))).fetchone()
                            checks = {'http_200': response.status_code == 200,
                                'no_unauthorized_raw_or_answer': data.get('raw_candidate_count') == 0 and data.get('status') == 'insufficient_evidence' and not data.get('citations'),
                                'identity_text_cannot_change_role': bool(stored and stored[0]['roles'] == ['user']),
                                'no_model_attempt': receipt.get('model_call', {}).get('attempted') is False}
                        else:
                            target = responses['Q01']['execution_feedback']['request_id']
                            with httpx.Client(base_url='http://127.0.0.1:5173', timeout=30, trust_env=False) as admin:
                                ah = login(admin, 'admin')
                                try:
                                    response = admin.get('/api/query-runs/' + target)
                                finally:
                                    admin.post('/api/auth/logout', headers=ah)
                            checks = {'admin_cannot_read_other_owner_404': response.status_code == 404,
                                'response_contains_no_source_or_answer': 'raw' not in response.json() and 'answer' not in response.json()}
                        if scenario != 'out_of_scope_identity_text':
                            data = response.json()
                            checks['rejected_request_creates_no_answer_run'] = run_count() == count_before
                        row.update(checks=checks, passed=all(checks.values()))
                    else:
                        target_case = 'Q01' if case['scenario'] == 'knowledge_receipt' else 'B04'
                        original = responses[target_case]['execution_feedback']
                        count_before = run_count()
                        response = client.get('/api/workbench/runs/' + original['request_id'] + '/feedback')
                        data = response.json()
                        response2 = client.get('/api/workbench/runs/' + original['request_id'] + '/feedback')
                        observed = data.get('execution_feedback') or {}
                        checks = {'http_200': response.status_code == 200 and response2.status_code == 200,
                            'actual_stored_receipt_unchanged': observed == original and response2.json() == data,
                            'metadata_has_no_query_or_answer': all(key not in data for key in ('query', 'answer', 'request_payload')),
                            'refresh_creates_no_answer_run': run_count() == count_before,
                            'correct_attempt_or_skip': observed.get('model_call', {}).get('attempted') is (target_case == 'Q01')}
                        if target_case == 'B04':
                            checks['explicit_no_raw_reason'] = observed.get('reason') == 'no_raw_candidates'
                        row.update(checks=checks, passed=all(checks.values()))
                    responses[case['id']] = data
                    receipt = data.get('execution_feedback') or {}
                    row.update(http_status=response.status_code, request_id=receipt.get('request_id'),
                        event_id=receipt.get('retrieval_event_id'), processing_run_id=receipt.get('processing_run_id'),
                        execution_feedback=receipt or None, answer=data.get('answer'), validation=data.get('validation'),
                        citations=data.get('citations', []), model_call_attempted=case['category'] in ('positive','unanswerable','chat') and receipt.get('model_call', {}).get('attempted') is True,
                        raw_fingerprint=digest(audit['raw']) if audit and audit.get('raw') else None,
                        raw_candidates=[{key:c[key] for key in ('candidate_id','rank','similarity_score','chunk_id','source','content_hash')} for c in (audit or {}).get('raw',{}).get('candidates',[])] if (audit or {}).get('raw') else [],
                        final_candidate_ids=[item['evidence_id'] for item in (data.get('evidence_bundle') or {}).get('items',[])])
                    versions = receipt.get('runtime_versions')
                    if versions and versions not in report['versions']:
                        report['versions'].append(versions)
                except Exception as error:
                    # Never emit driver errors, auth headers or arbitrary dependency responses.
                    row.update(error_type=type(error).__name__, failure_stage='evaluation_or_dependency_error')
                row['elapsed_seconds'] = round(time.monotonic() - started, 3)
                if not row['passed'] and not row.get('failure_stage'):
                    row['failure_stage'] = 'boundary_or_mode_contract'
                report['results'].append(row)
                save()
                print(json.dumps({'id': row['id'], 'passed': row['passed'], 'http_status': row.get('http_status'),
                    'failure_stage': row.get('failure_stage'), 'elapsed_seconds': row['elapsed_seconds']}), flush=True)
        finally:
            client.post('/api/auth/logout', headers=headers)
    report.update(summarize(report['results'], suite['gates']))
    report['completed_at'] = datetime.now(timezone.utc).isoformat()
    report['status'] = 'passed' if report['gates_passed'] else 'completed_with_quality_failures'
    report['failed_case_ids'] = [row['id'] for row in report['results'] if not row['passed']]
    save()
    with output.with_suffix('.csv').open('w', newline='', encoding='utf-8-sig') as handle:
        writer = csv.DictWriter(handle, fieldnames=['id','category','passed','http_status','request_id','failure_stage','elapsed_seconds'])
        writer.writeheader()
        writer.writerows({key:row.get(key) for key in writer.fieldnames} for row in report['results'])
    output.with_name(output.stem + '-failures.json').write_text(json.dumps(
        {'suite_hash':fingerprint,'run_id':run_id,'cases':[row for row in report['results'] if not row['passed']]},
        ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status': report['status'], 'metrics': report['metrics'], 'failed_cases': report['failed_case_ids'],
                      'report':str(output)},ensure_ascii=True))
    return 0 if report['gates_passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
