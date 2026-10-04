"""Real unified chat acceptance; owned demo sessions and explicitly marked test signals."""
import argparse,json,sys,time
from pathlib import Path
from uuid import uuid4
from datetime import datetime,timezone
import httpx
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'backend'))
from app.config.core_settings import CoreSettings
from app.config.settings import Settings
from app.account.settings import IdentitySettings


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--live',action='store_true');parser.add_argument('--verify-persistence',type=Path)
    args=parser.parse_args()
    if not args.live:print('Preview: unified chat, streaming, feedback, owner/CSRF/idempotency and persistent history. Use --live.');return 0
    settings=Settings();identity=IdentitySettings()
    if identity.mode!='demo':raise ValueError('Local demo acceptance only')
    output=ROOT/'.runtime/workbench/conversation'/('run-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid4().hex[:8]+'.json')
    output.parent.mkdir(parents=True,exist_ok=True)
    report={'transport':'real_vite_bff_postgres_onnx_deepseek_langgraph','started_at':datetime.now(timezone.utc).isoformat(),'checks':[],'messages':[]}
    def save():output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    def check(name,okay):
        report['checks'].append({'name':name,'passed':bool(okay)});save();print(name, bool(okay),flush=True)
    def login(client,user):
        r=client.post('/api/auth/demo-login',headers={'Origin':identity.public_origin},json={'username':user,'password':settings.user_accounts[user][0]})
        if r.status_code!=200:raise ValueError('Demo login failed')
        return {'Origin':identity.public_origin,'X-CSRF-Token':client.get('/api/auth/session').json()['csrf_token']}
    def post(client,headers,thread,message,*,stream=False,id=None):
        body={'message':message,'client_message_id':id or str(uuid4()),'origin':'automated_test'}
        events=[];started=time.monotonic()
        if stream:
            with client.stream('POST',f'/api/chat/{thread}/messages',headers={**headers,'Accept':'text/event-stream'},json=body) as response:
                if response.status_code!=200:raise ValueError('Stream request failed')
                for line in response.iter_lines():
                    if line.startswith('data:'):events.append(json.loads(line[5:]))
            data=next((e['data'] for e in events if e['type']=='result'),{})
        else:
            response=client.post(f'/api/chat/{thread}/messages',headers=headers,json=body)
            data=response.json() if response.status_code==200 else {}
        report['messages'].append({'input':body,'output':data,'http_status':response.status_code,
            'elapsed_seconds':round(time.monotonic()-started,3),'stream_event_types':[e['type'] for e in events],
            'nodes':[e['node'] for e in events if e['type']=='status'],'token_count':sum(e['type']=='token' for e in events)})
        save();return data,body,events
    with httpx.Client(base_url=identity.public_origin,timeout=180,trust_env=False) as client:
        headers=login(client,'test')
        try:
            access=client.get('/api/access-context').json()
            check('server_principal',access.get('user_id')=='test' and access.get('roles')==['user'] and access.get('tenant_id')=='enterprise-rag-bench-validation')
            if args.verify_persistence:
                parent=json.loads(args.verify_persistence.read_text(encoding='utf-8'));thread=parent['memory_thread']
                report['parent_report']=str(args.verify_persistence.resolve());report['memory_thread']=thread
                history=client.get(f'/api/chat/{thread}/messages').json()
                check('history_after_backend_restart',any('ORION-HTTP-42' in (item.get('message') or '') for item in history.get('items',[])))
                result,_,_=post(client,headers,thread,'刚才让你记住的聊天测试代码是什么？只回复代码。')
                check('checkpoint_memory_after_restart',result.get('kind')=='general_chat' and 'ORION-HTTP-42' in result.get('message',''))
            else:
                with httpx.Client(base_url=identity.public_origin,trust_env=False) as anonymous:
                    check('anonymous_401',anonymous.get('/api/chat/threads').status_code==401)
                check('csrf_403',client.post('/api/chat/threads',headers={'Origin':identity.public_origin},json={}).status_code==403)
                created=client.post('/api/chat/threads',headers=headers,json={});check('create_thread',created.status_code==200)
                thread=created.json()['thread_id'];report['memory_thread']=thread
                check('caller_mode_rejected',client.post(f'/api/chat/{thread}/messages',headers=headers,json={'message':'hello','mode':'knowledge'}).status_code==422)
                check('caller_identity_rejected',client.post(f'/api/chat/{thread}/messages',headers=headers,json={'message':'hello','tenant_id':'other','roles':['admin']}).status_code==422)
                with httpx.Client(base_url=identity.public_origin,timeout=60,trust_env=False) as admin:
                    ah=login(admin,'admin')
                    check('admin_cross_owner_read_404',admin.get(f'/api/chat/{thread}/messages').status_code==404)
                    check('admin_cross_owner_write_404',admin.post(f'/api/chat/{thread}/messages',headers=ah,json={'message':'hello'}).status_code==404)
                    admin.post('/api/auth/logout',headers=ah)
                direct,body,events=post(client,headers,thread,'记住本次聊天测试代码 ORION-HTTP-42。只需确认。',stream=True)
                check('automatic_direct',direct.get('kind')=='general_chat' and direct.get('route',{}).get('needs_retrieval') is False)
                check('stream_has_nodes_and_provider_tokens',{'analyze','direct','answer'}.issubset({e.get('node') for e in events}) and any(e.get('source')=='provider' for e in events))
                before=len(client.get(f'/api/chat/{thread}/messages').json().get('items',[]))
                replay=client.post(f'/api/chat/{thread}/messages',headers=headers,json=body).json()
                after=len(client.get(f'/api/chat/{thread}/messages').json().get('items',[]))
                check('message_replay_no_new_turn',replay.get('replayed') is True and replay.get('result')==direct.get('result') and before==after)
                check('same_message_id_different_body_409',client.post(f'/api/chat/{thread}/messages',headers=headers,json={**body,'message':'different'}).status_code==409)
                history=client.get(f'/api/chat/{thread}/messages').json()
                check('owned_business_transcript',len(history.get('items',[]))==1 and history['items'][0]['response']==direct)
                memory,_,_=post(client,headers,thread,'刚才让你记住的聊天测试代码是什么？只回复代码。')
                check('server_context_memory',memory.get('kind')=='general_chat' and 'ORION-HTTP-42' in memory.get('message',''))
                knowledge_thread=client.post('/api/chat/threads',headers=headers,json={}).json()['thread_id'];report['knowledge_thread']=knowledge_thread
                suite=json.loads((ROOT/'evals/workbench-smoke-26-v1.json').read_text(encoding='utf-8'))
                q=next(c['query'] for c in suite['cases'] if c['id']=='Q09')
                knowledge,_,events=post(client,headers,knowledge_thread,q,stream=True)
                result=knowledge.get('result') or {}
                check('automatic_authorized_rag',knowledge.get('kind')=='knowledge' and result.get('validation')=='source_and_quote_checked' and bool(result.get('citations')))
                check('rag_stream_after_verification',any(e.get('source')=='verified_result' for e in events) and not any(e.get('source')=='provider' for e in events))
                correction,body,_=post(client,headers,knowledge_thread,'你刚才回答不完整，请重新查资料：'+q)
                feedback=correction.get('feedback') or {};route=correction.get('route') or {}
                check('feedback_and_retrieval_both',route.get('is_feedback') is True and route.get('needs_retrieval') is True and correction.get('kind')=='knowledge')
                check('feedback_actual_prior_run_unreviewed',feedback.get('request_id')==result.get('request_id') and feedback.get('origin')=='automated_test' and feedback.get('review_state')=='unreviewed' and feedback.get('training_eligible') is False)
                repeated=client.post(f'/api/chat/{knowledge_thread}/messages',headers=headers,json=body).json()
                check('combined_replay_keeps_feedback_and_run',repeated.get('replayed') is True and repeated.get('feedback')==feedback and repeated.get('result')==correction.get('result'))
                status,_,_=post(client,headers,knowledge_thread,'上一条回答有没有调用 DeepSeek？请读实际系统回执。')
                check('system_receipt_is_actual_prior_run',status.get('kind')=='system' and status.get('execution_feedback')==correction.get('execution_feedback'))
                check('routing_call_separate_from_answer_call',status.get('routing_call',{}).get('status')=='succeeded' and status.get('result') is None)
                nq=next(c['query'] for c in suite['cases'] if c['id']=='N01')
                absent,_,_=post(client,headers,knowledge_thread,nq)
                check('automatic_abstention',absent.get('kind')=='knowledge' and (absent.get('result') or {}).get('status')=='insufficient_evidence' and not (absent.get('result') or {}).get('citations'))
        finally:client.post('/api/auth/logout',headers=headers)
    report['passed']=all(c['passed'] for c in report['checks']);report['completed_at']=datetime.now(timezone.utc).isoformat();save()
    print(json.dumps({'passed':report['passed'],'checks':len(report['checks']),'report':str(output)}));return 0 if report['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
