import copy
import hashlib
import json
from pathlib import Path
import pytest
from app.evaluation.semantic_acceptance import digest, gold_ranking, score_knowledge, summarize, validate_suite

ROOT = Path(__file__).resolve().parents[2]


def fixture():
    config = {'provider':'onnxruntime','model':'test','revision':'test','dimensions':1}
    source = {'document_id':'document-1','document_version':'v1','content_hash':hashlib.sha256(b'first 14 days').hexdigest()}
    raw = {'candidate_id':'candidate-1','rank':1,'text':'first 14 days','content_hash':source['content_hash'],'source':source}
    versions = {key:'v1' for key in ('runtime_fingerprint','policy_bundle_version','retrieval_profile_version',
        'model_revision','parser_version','prompt_version','processing_configuration_version')}
    receipt = {'request_id':'run-1','retrieval_event_id':'event-1','processing_run_id':'processing-1',
        'runtime_versions':versions,'model_call':{'attempted':True}}
    chain = {'content':{'text':raw['text']},'checks':{key:{'status':'pass'} for key in
        ('source_identity','source_version','source_locator','content_integrity','raw_link')}}
    response = {'status':'answered','answer':raw['text'],'validation':'source_and_quote_checked',
        'processing_run_id':'processing-1','execution_feedback':receipt,'runtime_versions':versions,
        'citations':[{'evidence_id':'candidate-1','quote':raw['text'],'source':source}],
        'evidence_bundle':{'items':[{'evidence_id':'candidate-1','source':source,'chain':chain}]}}
    audit = {'tenant_id':'tenant-1','run':{'actor_user_id':'test','request_id':'run-1','execution_feedback':receipt},
        'raw':{'event':{'id':'event-1','embedding_configuration':config},'candidates':[raw]}}
    case = {'category':'positive','gold_units':[{'document_id':'document-1','document_version':'v1','anchor':'14 days'}],
        'answer_terms':['14 days']}
    return case,response,audit,{'tenant_id':'tenant-1','embedding_signature':digest(config)}


def test_known_quote_can_be_irrelevant():
    case,response,audit,suite = fixture()
    case['answer_terms'] = ['medical reimbursement amount']
    result = score_knowledge(case,200,response,audit,suite)
    assert result['checks']['exact_citations_and_sources'] and not result['passed']
    assert result['failure_stage'] == 'answer_or_contract'


def test_full_known_case():
    case,response,audit,suite = fixture()
    result = score_knowledge(case,200,response,audit,suite)
    assert result['passed'] and result['raw_gold']['recall'] == result['final_gold']['recall'] == 1


@pytest.mark.parametrize('change',['text_hash','quote','chain','signature','owner'])
def test_failed_boundary_or_contract_cannot_be_success(change):
    case,response,audit,suite = fixture()
    if change == 'text_hash': audit['raw']['candidates'][0]['text'] = 'tampered'
    if change == 'quote': response['citations'][0]['quote'] = 'fabricated'
    if change == 'chain': response['evidence_bundle']['items'][0]['chain']['checks']['raw_link']['status'] = 'unknown'
    if change == 'signature': suite['embedding_signature'] = 'wrong'
    if change == 'owner': audit['run']['actor_user_id'] = 'admin'
    assert not score_knowledge(case,200,response,audit,suite)['passed']


def test_gold_requires_same_source_version_and_partial_recall_is_not_one():
    units = [{'document_id':'a','document_version':'v1','anchor':'first fact'},
             {'document_id':'a','document_version':'v1','anchor':'second fact'}]
    candidates = [{'source':{'document_id':'other','document_version':'v1'},'text':'first fact second fact'},
        {'source':{'document_id':'a','document_version':'old'},'text':'first fact second fact'},
        {'source':{'document_id':'a','document_version':'v1'},'text':'first fact'}]
    result = gold_ranking(units,candidates)
    assert result['ranks'] == [3,None] and result['recall'] == .5 and result['reciprocal_rank'] == 1/3


def test_raw_loss_and_final_loss_are_separate():
    case,response,audit,suite = fixture()
    response['evidence_bundle']['items'] = []
    response.update(status='insufficient_evidence',answer='',validation='no_verified_answer',citations=[])
    assert score_knowledge(case,200,response,audit,suite)['failure_stage'] == 'final_evidence'
    audit['raw']['candidates'] = []
    assert score_knowledge(case,200,response,audit,suite)['failure_stage'] == 'raw_retrieval'


def test_abstention_and_transport_failure():
    _,response,audit,suite = fixture()
    case = {'category':'unanswerable'}
    assert not score_knowledge(case,200,response,audit,suite)['passed']
    response.update(status='insufficient_evidence',validation='no_verified_answer',citations=[])
    assert score_knowledge(case,200,response,audit,suite)['passed']
    assert score_knowledge(case,503,response,None,suite)['failure_stage'] == 'transport_or_audit'


def test_failed_cases_remain_in_denominators_and_missing_categories_are_unknown():
    rows = [{'category':'positive','passed':True,'raw_gold':{'recall':1,'reciprocal_rank':.5},
        'final_gold':{'recall':1},'elapsed_seconds':10,'model_call_attempted':True},
        {'category':'positive','passed':False,'elapsed_seconds':30,'model_call_attempted':True},
        {'category':'receipt','passed':True,'elapsed_seconds':.2,'model_call_attempted':False}]
    report = summarize(rows,{'positive_answer_rate':.9,'receipt_pass_rate':1,'boundary_pass_rate':1})
    assert report['metrics']['positive_answer_rate'] == report['metrics']['raw_gold_recall_at_20'] == .5
    assert report['metrics']['latency_p95_seconds'] == 30 and report['metrics']['model_attempted_cases'] == 2
    assert report['metrics']['estimated_cost'] is None and not report['gates_passed']
    assert report['metrics']['boundary_pass_rate'] is None


def test_source_validation_happens_before_live_requests(tmp_path):
    data = {'sources':[{'document_id':'a','document_version':'v1','relative_path':'a.txt',
        'content_hash':hashlib.sha256(b'original').hexdigest()}],'gates':{'positive_answer_rate':.9},
        'cases':[{'id':str(i),'category':kind,'query':'question',
            **({'gold_units':[{'document_id':'a','document_version':'v1','anchor':'original'}],
                'answer_terms':['original']} if kind=='positive' else {})} for i,kind in enumerate(
            ['positive','unanswerable','boundary','chat','receipt']*4)]}
    (tmp_path/'a.txt').write_text('original',encoding='utf-8')
    assert len(validate_suite(data,tmp_path)) == 64
    duplicate = copy.deepcopy(data);duplicate['cases'][1]['id']='0'
    with pytest.raises(ValueError): validate_suite(duplicate,tmp_path)
    changed = copy.deepcopy(data);changed['cases'][0]['gold_units'][0]['document_version']='old'
    with pytest.raises(ValueError): validate_suite(changed,tmp_path)
    escape = copy.deepcopy(data);escape['sources'][0]['relative_path']='../a.txt'
    with pytest.raises(ValueError): validate_suite(escape,tmp_path)
    (tmp_path/'a.txt').write_text('changed',encoding='utf-8')
    with pytest.raises(ValueError): validate_suite(data,tmp_path)


def test_frozen_suite_size_and_category_counts():
    suite = json.loads((ROOT/'evals/workbench-smoke-26-v1.json').read_text(encoding='utf-8'))
    assert len(suite['cases']) == 26 and len({c['id'] for c in suite['cases']}) == 26
    assert len([c for c in suite['cases'] if c['category']=='positive']) == 12


def test_failed_model_output_keeps_actual_final_gold_from_processing():
    case,response,audit,suite=fixture()
    receipt=response['execution_feedback'];receipt['model_call']={'attempted':True,'error_code':'unverified_excerpt_response'}
    audit['run']['execution_feedback']=receipt
    audit['processing']=[{'id':'processing-1','selected_candidate_ids':['candidate-1']}]
    response={'execution_feedback':receipt,'processing_run_id':'processing-1'}
    result=score_knowledge(case,503,response,audit,suite)
    assert not result['passed'] and result['failure_stage']=='answer_validation'
    assert result['raw_gold']['recall']==result['final_gold']['recall']==1
