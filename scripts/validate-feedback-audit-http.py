"""Explicit local BFF/PG/Cedar acceptance; writes marked test feedback, calls no models."""
import argparse
import atexit
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from uuid import uuid4
import httpx

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from app.account.settings import IdentitySettings
from app.config.settings import settings
from app.config.core_settings import CoreSettings
from app.knowledge.contracts import content_hash
from app.knowledge.postgres import PostgresDatabase


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live',action='store_true')
    args=parser.parse_args()
    if not args.live:
        print('Preview only. --live reads existing authorized runs and appends automated_test feedback through the local BFF; no model calls.')
        return 0
    identity=IdentitySettings().validate();config=CoreSettings()
    if identity.mode!='demo' or config.access_for_user('test','user').tenant_id!='enterprise-rag-bench-validation':
        raise ValueError('This acceptance requires the explicit demo validation tenant')
    report={'checked_at':datetime.now(timezone.utc).isoformat(),'status':'failed_or_interrupted',
            'transport':'real_web_proxy_bff_postgresql_cedar','checks':[],'feedback':[]}
    output=ROOT/'.runtime/workbench/feedback-audit-http.json'
    output.parent.mkdir(parents=True,exist_ok=True)
    atexit.register(lambda:output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'))
    def check(name,ok):
        if not ok:raise AssertionError(name)
        report['checks'].append(name)
    def login(api,user):
        response=api.post('/api/auth/demo-login',headers={'Origin':identity.public_origin},
            json={'username':user,'password':settings.user_accounts[user][0]})
        check(user+'_authenticated_bff',response.status_code==200)
        session=api.get('/api/auth/session').json()
        return {'Origin':identity.public_origin,'X-CSRF-Token':session['csrf_token']}
    def get(api,path,name):
        response=api.get(path)
        check(name+'_http200',response.status_code==200)
        check(name+'_private_no_store',response.headers.get('Cache-Control')=='no-store')
        return response.json()
    with httpx.Client(base_url='http://127.0.0.1:5173',timeout=60,trust_env=False) as api:
        check('anonymous_audit_401',api.get('/api/query-runs').status_code==401)
        check('anonymous_feedback_401',api.post('/api/feedback',json={}).status_code==401)
        headers=login(api,'test')
        try:
            listing=get(api,'/api/query-runs?mode=knowledge&status=answered','authorized_knowledge_list')
            check('list_is_metadata_only',bool(listing['items']) and all('query' not in row and 'answer' not in row for row in listing['items']))
            selected=listing['items'][0];request_id=selected['request_id']
            before=get(api,'/api/query-runs/'+request_id,'knowledge_detail')
            check('actual_actor_and_tenant',before['run']['actor_user_id']=='test' and before['tenant_id']=='enterprise-rag-bench-validation')
            check('actual_raw_chain_and_answer',before['content_access']=='available' and before['raw'] and before['answer']['evidence_bundle'] and before['answer']['validation']=='source_and_quote_checked')
            event_id=before['raw']['event']['id'];candidate_id=before['answer']['citations'][0]['evidence_id']
            check('processing_and_citation_same_event',before['run']['execution_feedback']['retrieval_event_id']==event_id and any(candidate_id in run['selected_candidate_ids'] for run in before['processing']))
            report.update(request_id=request_id,event_id=event_id,candidate_id=candidate_id)
            check('missing_csrf_feedback_403',api.post('/api/feedback',headers={'Origin':identity.public_origin},json={}).status_code==403)
            base={'request_id':request_id,'event_id':event_id,'idempotency_key':'http-'+uuid4().hex,
                  'kind':'answer_helpfulness','value':'helpful','origin':'automated_test'}
            check('caller_cannot_supply_actor_or_confirmation',api.post('/api/feedback',headers=headers,json={**base,'actor_user_id':'admin','approved':True}).status_code==422)
            first=api.post('/api/feedback',headers=headers,json=base)
            check('helpfulness_saved_201',first.status_code==201)
            saved=first.json()['feedback'];report['feedback'].append(saved)
            replay=api.post('/api/feedback',headers=headers,json=base)
            check('retry_replays_same_id_and_time',replay.status_code==200 and replay.json()['replayed'] and replay.json()['feedback']==saved)
            check('same_key_different_value_409',api.post('/api/feedback',headers=headers,json={**base,'value':'not_helpful'}).status_code==409)
            check('wrong_event_400',api.post('/api/feedback',headers=headers,json={**base,'idempotency_key':'http-'+uuid4().hex,'event_id':'different-event'}).status_code==400)
            candidate={**base,'idempotency_key':'http-'+uuid4().hex,'kind':'candidate_relevance','value':'relevant','candidate_id':candidate_id}
            signal=api.post('/api/feedback',headers=headers,json=candidate)
            check('candidate_feedback_saved_201',signal.status_code==201)
            report['feedback'].append(signal.json()['feedback'])
            check('wrong_candidate_400',api.post('/api/feedback',headers=headers,json={**candidate,'idempotency_key':'http-'+uuid4().hex,'candidate_id':'candidate-from-another-event'}).status_code==400)
            correction={**base,'idempotency_key':'http-'+uuid4().hex,'kind':'factual_correction','value':'correction',
                'comment':'自动化接口验证：仅验证纠错信号写入，不声明答案存在事实错误。'}
            amended=api.post('/api/feedback',headers=headers,json=correction)
            check('correction_separate_saved_201',amended.status_code==201)
            report['feedback'].append(amended.json()['feedback'])
            check('all_signals_unreviewed_and_not_training',all(row['actor_user_id']=='test' and row['origin']=='automated_test' and row['review_state']=='unreviewed' and row['training_eligible'] is False for row in report['feedback']))
            after=get(api,'/api/query-runs/'+request_id,'audit_after_feedback')
            check('feedback_count_incremented_exactly_three',after['run']['feedback_count']==before['run']['feedback_count']+3)
            check('raw_and_answer_never_rewritten',after['raw']==before['raw'] and after['answer']==before['answer'] and after['processing']==before['processing'])
            added={row['id'] for row in report['feedback']}
            check('all_feedback_visible_in_audit',added.issubset({row['id'] for row in after['feedback']}))
            value=[row for row in after['evaluations'] if row['id']==signal.json()['feedback']['id']]
            check('only_candidate_signal_links_evaluation',len(value)==1 and value[0]['evaluator']=='user_feedback' and value[0]['candidate_id']==candidate_id and not added.intersection({row['id'] for row in after['evaluations']}-{value[0]['id']}))
            event=get(api,'/api/retrieval-events/'+event_id,'event_audit')
            check('event_endpoint_matches_same_raw',event['raw']==before['raw'] and event['request_id']==request_id)
            page=get(api,'/api/query-runs?limit=1','bounded_first_page')
            check('page_has_cursor_and_one_item',len(page['items'])==1 and bool(page['next_cursor']))
            next_page=get(api,'/api/query-runs?limit=1&cursor='+page['next_cursor'],'bounded_next_page')
            check('cursor_has_no_duplicate_request',next_page['items'][0]['request_id']!=page['items'][0]['request_id'])
            check('invalid_cursor_400',api.get('/api/query-runs?cursor=invalid!').status_code==400)
            check('oversized_page_422',api.get('/api/query-runs?limit=100').status_code==422)
            general_list=get(api,'/api/query-runs?mode=general_chat','ordinary_list')
            ordinary=get(api,'/api/query-runs/'+general_list['items'][0]['request_id'],'ordinary_detail')
            check('ordinary_history_without_retrieval',ordinary['raw'] is None and ordinary['answer']['validation']=='unverified_general_response' and not ordinary['answer']['citations'])
            with httpx.Client(base_url='http://127.0.0.1:5173',timeout=30,trust_env=False) as admin:
                admin_headers=login(admin,'admin')
                try:
                    check('another_actor_audit_404',admin.get('/api/query-runs/'+request_id).status_code==404)
                    check('another_actor_feedback_404',admin.post('/api/feedback',headers=admin_headers,json=base).status_code==404)
                    check('another_actor_event_404',admin.get('/api/retrieval-events/'+event_id).status_code==404)
                finally:admin.post('/api/auth/logout',headers=admin_headers)
            with PostgresDatabase().connection() as connection:
                rows=connection.execute('''SELECT id,actor_user_id,event_id,review_state,training_eligible,origin
                    FROM qa.user_feedback WHERE tenant_id=%s AND id=ANY(%s::text[])''',
                    (before['tenant_id'],list(added))).fetchall()
                check('three_actual_pg_feedback_rows',len(rows)==3 and all(row[1]=='test' and row[2]==event_id and row[3]=='unreviewed' and row[4] is False and row[5]=='automated_test' for row in rows))
                counts=connection.execute('''SELECT decision,count(*) FROM qa.authorization_events
                    WHERE tenant_id=%s AND resource_id=%s GROUP BY decision''',(before['tenant_id'],request_id)).fetchall()
                check('actual_cedar_allow_and_deny_events',dict(counts).get('allow',0)>0 and dict(counts).get('deny',0)>=2)
                report['migration_version']=connection.execute('SELECT version_num FROM core.alembic_version').fetchone()[0]
            report['raw_fingerprint']=content_hash(json.dumps(before['raw'],sort_keys=True,separators=(',',':'),ensure_ascii=False))
        finally:api.post('/api/auth/logout',headers=headers)
    report['status']='passed';report['check_count']=len(report['checks'])
    print(json.dumps({'status':'passed','checks':report['check_count'],'request_id':report['request_id'],'feedback_ids':[row['id'] for row in report['feedback']],'report':str(output)},ensure_ascii=True))
    return 0


if __name__=='__main__':raise SystemExit(main())
