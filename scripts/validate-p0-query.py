"""P0-3/4 acceptance through actual ASGI routes, PostgreSQL, local ONNX and DeepSeek."""

import argparse
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import sys
import time
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))

from app.config.core_settings import CoreSettings, CoreConfigurationError
from app.knowledge.contracts import content_hash
from app.knowledge.postgres import PostgresDatabase, DatabaseUnavailable
from app.providers.http import ProviderError

SYNTHETIC_POLICY = 'Synthetic validation policy: sick leave requires a medical certificate. This policy is made up for testing.'
SYNTHETIC_QUERY = 'What must be submitted for sick leave under the synthetic validation policy?'


class RollbackValidation(Exception):
    pass


class SharedDatabase:
    def __init__(self, settings, connection):
        self.settings = settings
        self.shared = connection

    @contextmanager
    def connection(self):
        yield self.shared


def validate(args, report, database=None):
    import httpx
    from fastapi.testclient import TestClient
    from app.api.routes.core_knowledge import get_core_query_service
    from app.config.settings import settings as account_settings
    from app.decision.grounded_answer import GroundedAnswerClient
    from app.retrieval.raw_journal import PostgresRawJournal
    from app.services.core_query_service import CoreQueryResponse, CoreQueryService
    from main import app

    for name in ('httpx','httpcore','orionstack.main','orionstack.auth'):
        logging.getLogger(name).setLevel(logging.WARNING)
    # Exercise the default policy without requiring Jev; the real DeepSeek key stays in memory.
    settings = replace(CoreSettings(),query_use_jev=False,typesafe_api_key='')
    if settings.embedding_provider != 'onnx':
        raise ValueError('P0 local acceptance requires ORIONSTACK_EMBEDDING_PROVIDER=onnx')
    database = database or PostgresDatabase(settings)
    service = CoreQueryService(database=database,settings=settings)
    access = settings.access_for_user(account_settings.test_user_username,'user')
    journal = PostgresRawJournal(database)
    captured = []
    retrieve = service.pipeline.retrieve
    def capture_retrieval(*positional, **keyword):
        result = retrieve(*positional,**keyword)
        captured.append(result)
        return result
    service.pipeline.retrieve = capture_retrieval
    local_transport = None
    if args.synthetic:
        real_answer = service.answer_client
        class SyntheticOnlyAnswer:
            def generate(self, context, candidates, principal):
                if (context.query != SYNTHETIC_QUERY or any(c.text != SYNTHETIC_POLICY for c in candidates)
                        or not principal.tenant_id.startswith('p0-synthetic-')):
                    raise ValueError('Synthetic live validation rejected unexpected evidence before network egress')
                return real_answer.generate(context,candidates,principal)
        service.answer_client = SyntheticOnlyAnswer()
        report['answer_transport'] = 'real_deepseek_fixed_synthetic_evidence_only'
    elif args.live_deepseek:
        real_answer = service.answer_client
        permitted_documents = frozenset(args.document_id)
        class ScopedExistingAnswer:
            def generate(self, context, candidates, principal):
                if (frozenset(context.document_ids) != permitted_documents
                        or any(c.source.document_id not in permitted_documents for c in candidates)):
                    raise ValueError('Live validation rejected evidence outside the explicitly selected documents')
                return real_answer.generate(context,candidates,principal)
        service.answer_client = ScopedExistingAnswer()
        report['answer_transport'] = 'real_deepseek_explicitly_selected_existing_documents'
        report['external_document_scope'] = sorted(permitted_documents)
    else:
        def local_answer(request):
            prompt = json.loads(json.loads(request.content)['messages'][-1]['content'])
            evidence = prompt['evidence'][0]
            return httpx.Response(200,json={'model':'local-contract-stub','choices':[{'finish_reason':'stop',
                'message':{'role':'assistant','content':json.dumps({'status':'answered',
                    'excerpts':[{'evidence_id':evidence['evidence_id'],'quote':evidence['text']}]})}}]})
        local_transport = httpx.Client(transport=httpx.MockTransport(local_answer))
        service.answer_client = GroundedAnswerClient(settings,local_transport)
        report['answer_transport'] = 'in_process_mock_no_network_egress'
    previous = dict(app.dependency_overrides)
    app.dependency_overrides[get_core_query_service] = lambda:service
    payload = {'query':args.query,'document_ids':args.document_id or [],'top_k':20,'final_top_k':5}
    try:
        # In-process ASGI uses the actual authentication/route stack, without starting/reconfiguring a server.
        with TestClient(app) as api:
            assert api.post('/api/query',json=payload).status_code==401,'Unauthenticated query was accepted'
            login = api.post('/api/v1/auth/login',json={'username':account_settings.test_user_username,
                'password':account_settings.test_user_password})
            assert login.status_code==200,'Configured regular account could not sign in'
            headers = {'Authorization':'Bearer '+login.json()['access_token']}
            assert login.json()['role']=='user'
            assert api.post('/api/query',json={**payload,'tenant_id':'foreign'},headers=headers).status_code==422
            assert api.post('/api/query',json={**payload,'entities':[{'type':'employee','id':'EMP-DEMO'}]},headers=headers).status_code==400
            assert not captured,'Rejected requests must not run retrieval'
            print(json.dumps({'phase':'authenticated_live_query','provider':'onnxruntime','jev_enabled':False}),flush=True)
            response = api.post('/api/query',json=payload,headers=headers)
            assert response.status_code==200,'Live query failed; HTTP '+str(response.status_code)
            answer = CoreQueryResponse.model_validate(response.json())
            assert answer.status=='answered' and answer.validation=='source_and_quote_checked' and answer.citations
            raw = journal.load_raw(answer.retrieval_event_id,access)
            assert raw==captured[-1].raw and raw.event.query==args.query and raw.event.query_hash==content_hash(args.query)
            assert raw.event.embedding_configuration.provider=='onnxruntime' and raw.event.user_id==access.user_id
            assert captured[-1].processing.processors==() and raw.event.tenant_id==access.tenant_id
            by_id = {c.candidate_id:c for c in raw.candidates}
            assert answer.answer=='\n\n'.join(c.quote for c in answer.citations)
            assert all(c.source==by_id[c.evidence_id].source and c.quote in by_id[c.evidence_id].text for c in answer.citations)
            with database.connection() as connection:
                saved = connection.execute('SELECT response FROM retrieval.answer_runs WHERE tenant_id=%s AND id=%s',
                    (access.tenant_id,answer.request_id)).fetchone()
                assert saved and saved[0]==answer.model_dump(mode='json')
            report['answered'] = {'http_status':response.status_code,'request_id':answer.request_id,
                'retrieval_event_id':answer.retrieval_event_id,'processing_run_id':answer.processing_run_id,
                'status':answer.status,'validation':answer.validation,'raw_candidates':answer.raw_candidate_count,
                'final_candidates':answer.final_candidate_count,'citations':len(answer.citations),
                'model':answer.model,'embedding_signature':raw.event.embedding_signature,
                'raw_roundtrip_exact':True,'answer_persisted_separately':True,'quotes_and_sources_match_raw':True,
                'regular_account_role':'user','tenant_id':access.tenant_id,'jev_enabled':False}
            print(json.dumps({'phase':'answered','raw_candidates':answer.raw_candidate_count,
                'citations':len(answer.citations)},ensure_ascii=True),flush=True)

            original_client = service.answer_client
            class ForbiddenAnswer:
                def generate(self,*unused): raise AssertionError('Empty recall invoked the answer provider')
            service.answer_client = ForbiddenAnswer()
            empty = api.post('/api/query',json={**payload,'document_ids':['p0-missing:'+str(uuid4())]},headers=headers)
            service.answer_client = original_client
            assert empty.status_code==200
            missing = CoreQueryResponse.model_validate(empty.json())
            assert missing.status=='insufficient_evidence' and not missing.citations and missing.raw_candidate_count==0
            assert not journal.load_raw(missing.retrieval_event_id,access).candidates
            report['empty_recall'] = {'http_status':empty.status_code,'retrieval_event_id':missing.retrieval_event_id,
                'status':missing.status,'raw_candidates':0,'answer_provider_called':False}

            if args.failure_check:
                with httpx.Client(transport=httpx.MockTransport(lambda request:httpx.Response(503,json={'error':'controlled_failure'}))) as failing:
                    service.answer_client = GroundedAnswerClient(settings,failing)
                    failed = api.post('/api/query',json=payload,headers=headers)
                service.answer_client = original_client
                assert failed.status_code==503 and failed.json()=={'detail':'Core query dependency is unavailable'}
                failed_raw = captured[-1].raw
                assert journal.load_raw(failed_raw.event.id,access)==failed_raw and failed_raw.candidates
                with database.connection() as connection:
                    audit = connection.execute('SELECT status,response FROM retrieval.answer_runs WHERE tenant_id=%s AND event_id=%s',
                        (access.tenant_id,failed_raw.event.id)).fetchone()
                    assert audit==('failed',{'status':'failed','error_code':'deepseek:http_error'})
                report['controlled_provider_failure'] = {'http_status':failed.status_code,
                    'retrieval_event_id':failed_raw.event.id,'raw_candidates':len(failed_raw.candidates),
                    'raw_preserved':True,'failed_answer_audit_saved':True,'response_redacted':True,
                    'provider_transport':'mock_503','retrieval_and_database':'real'}
            report['authentication'] = {'unauthenticated_http_status':401,'client_tenant_rejected_http_status':422,
                'unresolved_entities_http_status':400,'principal_from_server_binding':True}
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)
        if local_transport is not None:
            local_transport.close()


def validate_synthetic(args, report):
    from app.config.settings import settings as accounts
    from app.knowledge.contracts import AccessContext
    from app.knowledge.document_ingestion import DocumentKnowledgeService
    settings = CoreSettings()
    tenant = 'p0-synthetic-'+uuid4().hex
    old_bindings = os.environ.get('ORIONSTACK_CORE_PRINCIPALS')
    original_ids,original_query = args.document_id,args.query
    os.environ['ORIONSTACK_CORE_PRINCIPALS'] = json.dumps({accounts.test_user_username:
        {'tenant_id':tenant,'allowed_scopes':['internal']}})
    try:
        with PostgresDatabase(settings).connection() as connection:
            try:
                with connection.transaction():
                    shared = SharedDatabase(CoreSettings(),connection)
                    documents = DocumentKnowledgeService(shared)
                    access = AccessContext(tenant_id=tenant,user_id='synthetic-curator',roles=('admin',))
                    staged = documents.ingest('synthetic-validation-policy.txt',SYNTHETIC_POLICY.encode('utf-8'),access)
                    assert staged['status']=='active'
                    args.document_id,args.query = [staged['document_id']],SYNTHETIC_QUERY
                    validate(args,report,shared)
                    connection.execute('SET CONSTRAINTS ALL IMMEDIATE')
                    raise RollbackValidation()
            except RollbackValidation:
                pass
            assert connection.execute('SELECT count(*) FROM core.documents WHERE tenant_id=%s',(tenant,)).fetchone()[0]==0
            assert connection.execute('SELECT count(*) FROM retrieval.retrieval_event WHERE tenant_id=%s',(tenant,)).fetchone()[0]==0
            report['synthetic_database_transaction'] = 'all_test_rows_rolled_back_after_validation'
            report['existing_documents_sent_to_external_provider'] = False
    finally:
        args.document_id,args.query = original_ids,original_query
        if old_bindings is None:
            os.environ.pop('ORIONSTACK_CORE_PRINCIPALS',None)
        else:
            os.environ['ORIONSTACK_CORE_PRINCIPALS'] = old_bindings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live',action='store_true',help='Run real ASGI/ONNX/PostgreSQL validation; existing documents use an in-process answer stub')
    parser.add_argument('--synthetic',action='store_true',help='Call real DeepSeek only with fixed made-up query/evidence; roll back the isolated test tenant')
    parser.add_argument('--live-deepseek',action='store_true',help='Send explicitly selected existing document evidence to real DeepSeek; requires --live and --document-id')
    parser.add_argument('--query',default='病假需要提交什么材料？')
    parser.add_argument('--document-id',action='append')
    parser.add_argument('--failure-check',action='store_true',help='Also create a separate raw/failed audit using a controlled provider 503')
    parser.add_argument('--report',type=Path)
    args = parser.parse_args()
    if args.live_deepseek and (not args.live or args.synthetic or not args.document_id
                              or any(not doc.strip() for doc in args.document_id)):
        parser.error('--live-deepseek requires --live and nonempty --document-id, and cannot use --synthetic')
    start = time.monotonic()
    report = {'created_at':datetime.now(timezone.utc).isoformat(),'mode':'live' if args.live else 'preview',
        'api_transport':'in_process_asgi','status':'configuration_checked','configuration':CoreSettings().configuration_status()}
    try:
        if args.live:
            if args.synthetic:
                validate_synthetic(args,report)
            else:
                validate(args,report)
            report['status']='passed'
        report['elapsed_seconds']=round(time.monotonic()-start,3)
        if args.report:
            args.report.parent.mkdir(parents=True,exist_ok=True)
            args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(report,ensure_ascii=True,indent=2),flush=True)
        return 0
    except (CoreConfigurationError,DatabaseUnavailable,ProviderError,ValueError,AssertionError,OSError) as error:
        print('[orionstack] P0 validation failed: '+(str(error) if isinstance(error,(AssertionError,ProviderError)) else type(error).__name__),file=sys.stderr)
        return 2


if __name__=='__main__': raise SystemExit(main())
