"""Feedback/audit bind to real principals and runs without upgrading user signals."""
import json
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from app.api.core_access import require_core_access
from app.api.routes.audit_feedback import get_run_audit_repository, get_user_feedback_repository
from app.security.cedar import CedarAuthorizer
from app.services.core_query_service import CoreQueryRequest
from app.workbench.audit import RunAuditRepository
from app.workbench.user_feedback import UserFeedbackRepository, FeedbackConflict
from app.workbench.audit_contracts import UserFeedbackRequest
from app.workbench.contracts import GeneralChatRequest
from app.workbench.service import GeneralChatService
from test_raw_postgres_integration import database, SqlFailure
from test_workbench_modes import knowledge, client, SETTINGS, READER
from test_p0_core import ADMIN
from main import app


def knowledge_run(database):
    import httpx
    from app.decision.grounded_answer import GroundedAnswerClient
    from test_workbench_modes import response
    def quote(request):
        item=json.loads(json.loads(request.content)['messages'][-1]['content'])['retrieved_evidence']['items'][0]
        return response(json.dumps({'status':'answered','excerpts':[{'evidence_id':item['evidence_id'],'quote':item['text']}]}))
    model=GroundedAnswerClient(SETTINGS,httpx.Client(transport=httpx.MockTransport(quote)))
    service,docs,document,journal=knowledge(database,model)
    answer=service.query(CoreQueryRequest(query='certificate'),ADMIN)
    return answer,docs,document,journal


def signal(answer,**changes):
    data={'request_id':answer.request_id,'idempotency_key':'acceptance-key-0001','kind':'answer_helpfulness','value':'helpful'}
    data.update(changes)
    return UserFeedbackRequest(**data)


@pytest.mark.parametrize('changes',[{'actor_user_id':'admin'},{'tenant_id':'foreign'},{'approved':True},
    {'evaluator':'human'},{'training_eligible':True},{'review_state':'approved'},
    {'kind':'candidate_relevance','value':'relevant'},{'kind':'answer_helpfulness','value':'relevant'},
    {'kind':'factual_correction','value':'correction','comment':'  '}])
def test_feedback_contract_never_accepts_identity_or_confirmation_claims(changes):
    with pytest.raises(ValidationError):
        UserFeedbackRequest.model_validate({'request_id':'real-id','idempotency_key':'valid-key-01',
            'kind':'answer_helpfulness','value':'helpful',**changes})


def test_helpfulness_idempotence_does_not_relabel_raw_or_candidates(database):
    answer,_,_,journal=knowledge_run(database)
    before=journal.load_raw(answer.retrieval_event_id,ADMIN)
    repo=UserFeedbackRepository(database)
    first=repo.submit(signal(answer),ADMIN);again=repo.submit(signal(answer),ADMIN)
    assert not first.replayed and again.replayed and first.feedback==again.feedback
    assert first.feedback.actor_user_id==ADMIN.user_id and first.feedback.event_id==answer.retrieval_event_id
    assert first.feedback.review_state=='unreviewed' and first.feedback.training_eligible is False
    assert database.bridge.execute('SELECT count(*) FROM qa.user_feedback').fetchone()[0]==1
    assert database.bridge.execute('SELECT count(*) FROM retrieval.retrieval_evaluation').fetchone()[0]==0
    assert journal.load_raw(answer.retrieval_event_id,ADMIN)==before
    with pytest.raises(FeedbackConflict):repo.submit(signal(answer,value='not_helpful'),ADMIN)


def test_candidate_signals_and_corrections_remain_separate_and_traceable(database):
    answer,_,_,journal=knowledge_run(database)
    candidate=journal.load_raw(answer.retrieval_event_id,ADMIN).candidates[0]
    repo=UserFeedbackRepository(database)
    request=signal(answer,kind='candidate_relevance',value='not_relevant',event_id=answer.retrieval_event_id,
        candidate_id=candidate.candidate_id,origin='automated_test')
    entry=repo.submit(request,ADMIN).feedback
    assert repo.submit(request,ADMIN).replayed
    correction=repo.submit(signal(answer,idempotency_key='correction-key-0001',kind='factual_correction',value='correction',
        comment='This is only a user report, never an approved label.'),ADMIN).feedback
    assert correction.candidate_id is None and correction.review_state=='unreviewed'
    audit=RunAuditRepository(database).read(answer.request_id,ADMIN)
    assert audit.raw==journal.load_raw(answer.retrieval_event_id,ADMIN)
    assert audit.answer.answer==answer.answer and audit.answer.evidence_bundle==answer.evidence_bundle
    assert len(audit.processing)==1 and audit.processing[0].selected_candidate_ids==(candidate.candidate_id,)
    assert len(audit.evaluations)==1 and audit.evaluations[0].id==entry.id
    details=json.loads(audit.evaluations[0].details_json)
    assert details['actor_user_id']==ADMIN.user_id and details['origin']=='automated_test' and details['training_eligible'] is False
    assert len(audit.feedback)==2 and audit.authorization[-1].policy_version


def test_foreign_event_and_candidate_are_rejected_with_no_feedback_write(database):
    answer,_,_,journal=knowledge_run(database)
    second,_,_,_=knowledge_run(database)
    repo=UserFeedbackRepository(database)
    with pytest.raises(ValueError):repo.submit(signal(answer,event_id=second.retrieval_event_id),ADMIN)
    other_candidate=journal.load_raw(second.retrieval_event_id,ADMIN).candidates[0].candidate_id
    with pytest.raises(ValueError):repo.submit(signal(answer,kind='candidate_relevance',value='relevant',
        event_id=answer.retrieval_event_id,candidate_id=other_candidate),ADMIN)
    assert database.bridge.execute('SELECT count(*) FROM qa.user_feedback').fetchone()[0]==0


def test_key_is_actor_scoped_and_cannot_silently_target_another_run(database):
    service=GeneralChatService(database,client(),SETTINGS)
    one=service.chat(GeneralChatRequest(query='first'),READER)
    two=service.chat(GeneralChatRequest(query='second'),READER)
    repo=UserFeedbackRepository(database)
    repo.submit(signal(one),READER)
    with pytest.raises(FeedbackConflict):repo.submit(signal(two),READER)
    another=READER.model_copy(update={'user_id':'another'})
    three=service.chat(GeneralChatRequest(query='third'),another)
    assert not repo.submit(signal(three),another).replayed


@pytest.mark.parametrize('change',[{'user_id':'another','roles':('admin',)},{'tenant_id':'foreign'}])
def test_owner_only_boundary_also_applies_to_admin_and_cross_tenant(database,change):
    answer,_,_,_=knowledge_run(database)
    other=ADMIN.model_copy(update=change)
    audit=RunAuditRepository(database)
    assert not audit.list_runs(other).items
    with pytest.raises(LookupError):audit.read(answer.request_id,other)
    with pytest.raises(LookupError):audit.read_event(answer.retrieval_event_id,other)
    with pytest.raises(LookupError):UserFeedbackRepository(database).submit(signal(answer),other)
    assert database.bridge.execute("SELECT count(*) FROM qa.authorization_events WHERE decision='deny'").fetchone()[0]>=2


@pytest.mark.parametrize('changed',['revoked','scope'])
def test_current_access_change_withholds_historical_content_but_preserves_raw(database,changed):
    answer,docs,document,journal=knowledge_run(database)
    before=journal.load_raw(answer.retrieval_event_id,ADMIN)
    repo=UserFeedbackRepository(database)
    repo.submit(signal(answer,comment='Medical certificate is required.'),ADMIN)
    current=ADMIN
    if changed=='revoked':docs.revoke(document['document_id'],ADMIN)
    else:current=ADMIN.model_copy(update={'allowed_scopes':()})
    audit=RunAuditRepository(database).read(answer.request_id,current)
    assert audit.content_access=='withheld' and audit.raw is None and audit.answer is None and audit.query is None
    assert not audit.processing and not audit.evaluations and audit.feedback[0].comment is None
    assert 'Medical certificate' not in audit.model_dump_json()
    assert audit.run.execution_feedback.request_id==answer.request_id
    with pytest.raises(LookupError):repo.submit(signal(answer),current)
    assert journal.load_raw(answer.retrieval_event_id,ADMIN)==before


def test_bounded_keyset_pages_and_filters_never_return_question_or_answer_text(database):
    service=GeneralChatService(database,client(),SETTINGS)
    with database.bridge.transaction():
        for i in range(3):service.chat(GeneralChatRequest(query='private-query-'+str(i)),READER)
    repo=RunAuditRepository(database)
    one=repo.list_runs(READER,limit=1,mode='general_chat',status='answered')
    two=repo.list_runs(READER,limit=1,cursor=one.next_cursor)
    three=repo.list_runs(READER,limit=1,cursor=two.next_cursor)
    assert len({one.items[0].request_id,two.items[0].request_id,three.items[0].request_id})==3 and three.next_cursor is None
    assert 'private-query' not in one.model_dump_json() and 'Hello' not in one.model_dump_json()
    assert repo.list_runs(READER,mode='knowledge').items==()
    with pytest.raises(ValueError):repo.list_runs(READER,cursor='invalid!')
    with pytest.raises(ValueError):repo.list_runs(READER,limit=51)


def test_general_audit_and_feedback_never_create_retrieval_records(database):
    answer=GeneralChatService(database,client(),SETTINGS).chat(GeneralChatRequest(query='hello'),READER)
    UserFeedbackRepository(database).submit(signal(answer),READER)
    audit=RunAuditRepository(database).read(answer.request_id,READER)
    assert audit.content_access=='available' and audit.answer.validation=='unverified_general_response'
    assert audit.raw is None and not audit.processing and not audit.evaluations and not audit.answer.citations
    assert database.bridge.execute('SELECT count(*) FROM retrieval.retrieval_event').fetchone()[0]==0


def test_cedar_deny_is_a_real_fail_closed_decision(database):
    answer=GeneralChatService(database,client(),SETTINGS).chat(GeneralChatRequest(query='hello'),READER)
    denied=CedarAuthorizer(policies='forbid(principal,action,resource);')
    repo=RunAuditRepository(database,denied)
    with pytest.raises(LookupError):repo.read(answer.request_id,READER)
    with pytest.raises(LookupError):UserFeedbackRepository(database,denied).submit(signal(answer),READER)
    row=database.bridge.execute('SELECT decision,policy_version,principal_id FROM qa.authorization_events LIMIT 1').fetchone()
    assert row==('deny',denied.version,READER.user_id)


def test_candidate_evaluation_and_feedback_commit_or_rollback_together(database,monkeypatch):
    answer,_,_,journal=knowledge_run(database)
    candidate=journal.load_raw(answer.retrieval_event_id,ADMIN).candidates[0].candidate_id
    original=database.bridge.execute
    def fail(sql,*args,**kwargs):
        if 'INSERT INTO retrieval.retrieval_evaluation' in sql:raise SqlFailure('forced failure','XX000')
        return original(sql,*args,**kwargs)
    monkeypatch.setattr(database.bridge,'execute',fail)
    with pytest.raises(SqlFailure):UserFeedbackRepository(database).submit(signal(answer,kind='candidate_relevance',value='relevant',
        event_id=answer.retrieval_event_id,candidate_id=candidate),ADMIN)
    assert original('SELECT count(*) FROM qa.user_feedback').fetchone()[0]==0
    assert original('SELECT count(*) FROM retrieval.retrieval_evaluation').fetchone()[0]==0


@pytest.mark.parametrize('table',['qa.user_feedback','qa.authorization_events','retrieval.retrieval_evaluation','retrieval.answer_runs'])
def test_domain_journal_cannot_be_rewritten_or_truncated(database,table):
    answer,_,_,journal=knowledge_run(database)
    candidate=journal.load_raw(answer.retrieval_event_id,ADMIN).candidates[0].candidate_id
    UserFeedbackRepository(database).submit(signal(answer,kind='candidate_relevance',value='relevant',event_id=answer.retrieval_event_id,candidate_id=candidate),ADMIN)
    for sql in ('DELETE FROM '+table,'TRUNCATE '+table+' CASCADE'):
        with pytest.raises(SqlFailure,match='immutable'):
            with database.bridge.transaction():database.bridge.execute(sql)


def test_http_feedback_and_audit_use_real_scoped_ids_and_compatible_errors(database):
    answer,_,_,_=knowledge_run(database)
    previous=dict(app.dependency_overrides)
    try:
        app.dependency_overrides[require_core_access]=lambda:ADMIN
        app.dependency_overrides[get_user_feedback_repository]=lambda:UserFeedbackRepository(database)
        app.dependency_overrides[get_run_audit_repository]=lambda:RunAuditRepository(database)
        with TestClient(app) as api:
            payload=signal(answer).model_dump(mode='json')
            saved=api.post('/api/feedback',json=payload)
            assert saved.status_code==201 and saved.json()['feedback']['actor_user_id']=='admin'
            replay=api.post('/api/feedback',json=payload)
            assert replay.status_code==200 and replay.json()['feedback']==saved.json()['feedback']
            assert api.post('/api/feedback',json={**payload,'value':'not_helpful'}).status_code==409
            assert api.post('/api/feedback',json={**payload,'actor_user_id':'forged'}).status_code==422
            assert api.get('/api/query-runs').status_code==200
            detail=api.get('/api/query-runs/'+answer.request_id)
            assert detail.status_code==200 and detail.json()['raw']['event']['id']==answer.retrieval_event_id
            assert api.get('/api/retrieval-events/'+answer.retrieval_event_id).status_code==200
            assert api.get('/api/query-runs?limit=100').status_code==422
            assert api.get('/api/query-runs?cursor=invalid!').status_code==400
            app.dependency_overrides[require_core_access]=lambda:ADMIN.model_copy(update={'user_id':'other'})
            assert api.get('/api/query-runs/'+answer.request_id).status_code==404
            assert api.post('/api/feedback',json=payload).status_code==404
    finally:
        app.dependency_overrides.clear();app.dependency_overrides.update(previous)
