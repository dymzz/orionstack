"""P0 races and malformed outputs must preserve raw facts and fail closed."""

import json

from fastapi.testclient import TestClient
import pytest

from app.api.auth import create_token
from app.api.routes.core_knowledge import get_core_document_service, get_core_query_service
from app.config.core_settings import CoreSettings
from app.decision.grounded_answer import CheckedCitation, GroundedAnswer
from app.knowledge.legacy_migration import LegacySnapshotPlanner, canonical_json
from app.knowledge.legacy_resolutions import resolve_missing_sources
from app.knowledge.contracts import content_hash
from app.knowledge.document_ingestion import DocumentKnowledgeService
from app.knowledge.postgres import MigrationError
from app.retrieval.postgres_vector import PostgresVectorRetriever
from app.retrieval.raw_journal import PostgresRawJournal
from app.retrieval.raw_pipeline import RawRetrievalPipeline
from app.services.core_query_service import CoreQueryRequest, CoreQueryService
from main import app
from test_raw_postgres_integration import database
from test_p0_core import ADMIN, FakeEmbedding, api_client


def test_configured_principal_map_denies_unbound_accounts(api_client, monkeypatch):
    bindings=json.dumps({'alice':{'tenant_id':'private','allowed_scopes':['internal']}})
    with pytest.raises(PermissionError):
        CoreSettings(principal_bindings_json=bindings).access_for_user('test','user')
    monkeypatch.setenv('ORIONSTACK_CORE_PRINCIPALS',bindings)
    app.dependency_overrides[get_core_query_service]=lambda:object()
    response=api_client.post('/api/query',json={'query':'hello'},headers={'Authorization':'Bearer '+create_token('test','user')})
    assert response.status_code==403


def test_quarantine_preserves_physical_line_numbers_and_rejects_partial_manifest(tmp_path):
    folder=tmp_path/'extracted_faqs';folder.mkdir(exist_ok=True)
    row={'unit_id':'broken','source_record_id':'missing','question':'Q?','answer':'A.'}
    (folder/'extracted_faqs.jsonl').write_text('\n\n'+json.dumps(row),encoding='utf-8')
    entry={'tenant_id':'custom','unit_id':'broken','source_record_id':'missing','operation':'quarantine',
           'reason':'untraceable','evidence':'reviewed fixture','expected_payload_hash':content_hash(canonical_json(row))}
    manifest=tmp_path/'resolutions.json'
    manifest.write_text(json.dumps({'schema_version':1,'resolutions':[entry,entry]}),encoding='utf-8')
    plan=LegacySnapshotPlanner(tmp_path,'custom').build(include_seed=False)
    before=list(plan.errors)
    with pytest.raises(MigrationError): resolve_missing_sources(plan,tmp_path,manifest,fallback_tenant='custom')
    assert plan.errors==before and not plan.quarantined
    manifest.write_text(json.dumps({'schema_version':1,'resolutions':[entry]}),encoding='utf-8')
    resolve_missing_sources(plan,tmp_path,manifest,fallback_tenant='custom')
    assert not plan.errors and plan.quarantined[0]['origin'].endswith(':3')


@pytest.mark.parametrize('change',['source_revoke','source_scope','new_version'])
def test_source_change_after_model_generation_invalidates_answer_but_keeps_raw(database,change):
    embed=FakeEmbedding();docs=DocumentKnowledgeService(database,embed)
    document=docs.ingest('policy.txt',b'Medical certificate is required.',ADMIN)
    journal=PostgresRawJournal(database)
    pipeline=RawRetrievalPipeline(embedding=embed,retriever=PostgresVectorRetriever(database,journal),journal=journal)
    class Answer:
        def generate(self,context,candidates,access):
            c=candidates[0]
            if change=='new_version':
                docs.ingest('policy.txt',b'The new policy replaces this passage.',ADMIN,document_id=document['document_id'])
            else:
                column,value=('lifecycle_status','revoked') if change=='source_revoke' else ('access_scope','restricted')
                database.bridge.execute(f'UPDATE core.source_records SET {column}=%s',(value,))
            return GroundedAnswer(status='answered',answer=c.text,citations=(CheckedCitation(evidence_id=c.evidence_id,quote=c.text,source=c.source),))
    result=CoreQueryService(database,pipeline,Answer()).query(CoreQueryRequest(query='medical certificate'),ADMIN)
    assert result.status=='insufficient_evidence' and not result.citations and result.final_candidate_count==0
    assert journal.load_raw(result.retrieval_event_id,ADMIN).candidates[0].text=='Medical certificate is required.'


@pytest.mark.parametrize('status',['answered','insufficient_evidence'])
def test_unverified_free_text_from_injected_model_never_reaches_answer(database,status):
    embed=FakeEmbedding();DocumentKnowledgeService(database,embed).ingest('policy.txt',b'Policy.',ADMIN)
    journal=PostgresRawJournal(database)
    pipeline=RawRetrievalPipeline(embedding=embed,retriever=PostgresVectorRetriever(database,journal),journal=journal)
    class Answer:
        def generate(self,context,candidates,access):
            c=candidates[0]
            return GroundedAnswer(status=status,answer='Unsupported statement.',citations=(CheckedCitation(evidence_id=c.evidence_id,quote=c.text,source=c.source),))
    result=CoreQueryService(database,pipeline,Answer()).query(CoreQueryRequest(query='policy'),ADMIN)
    assert result.status=='insufficient_evidence' and 'Unsupported' not in result.answer and not result.citations


def test_authenticated_content_download_is_exact_and_revocation_blocks_it(database,api_client,monkeypatch):
    docs=DocumentKnowledgeService(database,FakeEmbedding())
    document=docs.ingest('medical-policy.txt',b'Medical certificate is required.',ADMIN)
    monkeypatch.setenv('ORIONSTACK_CORE_PRINCIPALS',json.dumps({'test':{'tenant_id':'t1','allowed_scopes':['internal']}}))
    app.dependency_overrides[get_core_document_service]=lambda:docs
    path='/api/documents/'+document['document_id']+'/content'
    assert api_client.get(path).status_code==401
    headers={'Authorization':'Bearer '+create_token('test','user')}
    response=api_client.get(path,headers=headers)
    assert response.status_code==200 and response.content==b'Medical certificate is required.'
    assert response.headers['content-disposition'].startswith('attachment;')
    docs.revoke(document['document_id'],ADMIN)
    assert api_client.get(path,headers=headers).status_code==404
