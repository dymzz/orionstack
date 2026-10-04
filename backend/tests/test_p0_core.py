"""P0 source repair, authentication, quote verification and PostgreSQL lifecycle regressions."""

from contextlib import contextmanager
import json
from pathlib import Path

from fastapi.testclient import TestClient
import httpx
import pytest
from pydantic import ValidationError

from app.api.auth import create_token
from app.api.routes.core_knowledge import get_core_document_service, get_core_query_service
from app.config.core_settings import CoreSettings, CoreConfigurationError
from app.decision.grounded_answer import CheckedCitation, GroundedAnswer, GroundedAnswerClient, insufficient_answer
from app.knowledge.contracts import AccessContext, EvidenceCandidate, QueryContext, SourceRef, content_hash
from app.knowledge.document_ingestion import DocumentKnowledgeService
from app.knowledge.embedding import EmbeddingBatch, EmbeddingSignature
from app.knowledge.evidence_validity import EvidenceValidityRepository
from app.knowledge.legacy_migration import LegacySnapshotPlanner, canonical_json
from app.knowledge.legacy_resolutions import resolve_missing_sources
from app.providers.http import ProviderError
from app.retrieval.postgres_vector import EmbeddingWriteConflict, PostgresVectorRetriever
from app.retrieval.raw_contracts import ProcessingRun, RetrievalResponse
from app.retrieval.raw_journal import PostgresRawJournal
from app.retrieval.raw_pipeline import RawRetrievalPipeline
from app.services.core_query_service import CoreQueryRequest, CoreQueryResponse, CoreQueryService
from main import app
from test_raw_postgres_integration import database, SqlFailure
from test_raw_retrieval import raw_record, ACCESS


def evidence():
    return EvidenceCandidate(evidence_id="e1",evidence_kind="document_chunk",tenant_id="t1",access_scope="internal",
        text="病假需要医疗证明。年假需提前申请。",retrieval_method="vector",source=SourceRef(source_id="s1",source_version="v1",source_locator="doc://1"))


def model_response(draft, finish_reason="stop"):
    return {"model":"deepseek-test","choices":[{"finish_reason":finish_reason,"message":{"role":"assistant","content":json.dumps(draft,ensure_ascii=False)}}]}


def grounded_client(draft, finish_reason="stop"):
    return GroundedAnswerClient(CoreSettings(deepseek_api_key="fake-key"),httpx.Client(transport=httpx.MockTransport(
        lambda request:httpx.Response(200,json=model_response(draft,finish_reason)))))


def test_grounded_answer_is_entirely_built_from_verbatim_evidence():
    result=grounded_client({"status":"answered","excerpts":[{"evidence_id":"e1","quote":"病假需要医疗证明。"}]}).generate(
        QueryContext(query="病假材料"),(evidence(),),AccessContext(tenant_id="t1",user_id="u1"))
    assert result.answer=="病假需要医疗证明。"
    assert result.validation=="source_and_quote_checked"
    assert result.citations[0].source==evidence().source


@pytest.mark.parametrize("draft",[
    {"status":"answered","excerpts":[{"evidence_id":"forged","quote":"病假需要医疗证明。"}]},
    {"status":"answered","excerpts":[{"evidence_id":"e1","quote":"病假无需医疗证明。"}]},
    {"status":"answered","excerpts":[{"evidence_id":"e1","quote":" "}]},
    {"status":"answered","excerpts":[]},
    {"status":"insufficient_evidence","excerpts":[{"evidence_id":"e1","quote":"病假"}]},
    {"status":"answered","answer":"invented claim","excerpts":[{"evidence_id":"e1","quote":"病假"}]},
    {"status":"answered","excerpts":[{"evidence_id":"e1","quote":"病假","source":"invented"}]},
    {"status":"answered","excerpts":[{"evidence_id":"e1","quote":"病假"},{"evidence_id":"e1","quote":"病假"}]},
])
def test_invalid_or_forged_model_excerpt_cannot_be_returned(draft):
    with pytest.raises(ProviderError,match="unverified_excerpt_response"):
        grounded_client(draft).generate(QueryContext(query="病假材料"),(evidence(),),AccessContext(tenant_id="t1",user_id="u1"))


def test_empty_evidence_does_not_require_model_credentials_or_call_network():
    def forbidden(request): pytest.fail("No evidence must not call the model")
    result=GroundedAnswerClient(CoreSettings(deepseek_api_key=""),httpx.Client(transport=httpx.MockTransport(forbidden))).generate(
        QueryContext(query="missing"),(),AccessContext(tenant_id="t1",user_id="u1"))
    assert result.status=="insufficient_evidence" and not result.citations


def test_truncated_model_response_and_foreign_evidence_are_rejected():
    client=grounded_client({"status":"insufficient_evidence","excerpts":[]},"length")
    with pytest.raises(ProviderError): client.generate(QueryContext(query="x"),(evidence(),),AccessContext(tenant_id="t1",user_id="u1"))
    with pytest.raises(PermissionError): client.generate(QueryContext(query="x"),(evidence(),),AccessContext(tenant_id="other",user_id="u1"))


def test_core_principal_uses_server_binding_and_signed_account_role():
    settings=CoreSettings(principal_bindings_json=json.dumps({"alice":{"tenant_id":"tenant-a","allowed_scopes":["internal","restricted"]}}))
    principal=settings.access_for_user("alice","user")
    assert principal==AccessContext(tenant_id="tenant-a",user_id="alice",roles=("user",),allowed_scopes=("internal","restricted"))


@pytest.mark.parametrize("binding",["[]",'{"alice":{"tenant_id":"t1","allowed_scopes":"all"}}','{"alice":{"tenant_id":"t1","allowed_scopes":["internal"],"roles":["admin"]}}'])
def test_invalid_server_bindings_do_not_grant_permissions(binding):
    with pytest.raises(CoreConfigurationError): CoreSettings(principal_bindings_json=binding).access_for_user("alice","user")


@pytest.mark.parametrize("field,value",[("tenant_id","foreign"),("user_id","admin"),("roles",["admin"]),("allowed_scopes",["restricted"]),("with_jev",True)])
def test_query_contract_rejects_client_identity_or_processing_policy(field,value):
    with pytest.raises(ValidationError): CoreQueryRequest.model_validate({"query":"hello",field:value})


@pytest.fixture
def api_client():
    previous=dict(app.dependency_overrides)
    try: yield TestClient(app)
    finally: app.dependency_overrides.clear(); app.dependency_overrides.update(previous)


def test_query_authentication_and_server_principal(api_client):
    seen=[]
    class Service:
        def query(self,payload,access):
            seen.append(access)
            return CoreQueryResponse(**insufficient_answer().model_dump(),tenant_id=access.tenant_id,request_id="r",retrieval_event_id="e",processing_run_id="p",
                processing_status="completed",raw_candidate_count=0,final_candidate_count=0,checked_at="2026-10-03T00:00:00Z")
    app.dependency_overrides[get_core_query_service]=lambda:Service()
    assert api_client.post('/api/query',json={"query":"hello"}).status_code==401
    response=api_client.post('/api/query',json={"query":"hello"},headers={"Authorization":"Bearer "+create_token("test","user")})
    assert response.status_code==200 and seen[0].user_id=="test" and seen[0].roles==("user",)
    assert api_client.post('/api/query',json={"query":"hello","tenant_id":"other"},headers={"Authorization":"Bearer "+create_token("test","user")}).status_code==422


def test_document_upload_denies_regular_user_before_any_storage(api_client):
    class Service:
        def ingest(self,*args,**kwargs): pytest.fail("Unauthorized upload must not be stored")
    app.dependency_overrides[get_core_document_service]=lambda:Service()
    response=api_client.post('/api/documents',files={"file":("a.txt",b"policy")},headers={"Authorization":"Bearer "+create_token("test","user")})
    assert response.status_code==403


def test_query_provider_errors_are_redacted(api_client):
    class Service:
        def query(self,*args): raise ProviderError("deepseek","http_error",500)
    app.dependency_overrides[get_core_query_service]=lambda:Service()
    response=api_client.post('/api/query',json={"query":"hello"},headers={"Authorization":"Bearer "+create_token("test","user")})
    assert response.status_code==503 and response.json()=={"detail":"Core query dependency is unavailable"}


def test_reviewed_quarantine_preserves_history_and_requires_exact_hash(tmp_path):
    folder=tmp_path/'extracted_faqs';folder.mkdir(exist_ok=True)
    rows=[{"tenant_id":"t1","unit_id":"broken","source_record_id":"missing","question":"Q?","answer":"A.","published_at":stamp} for stamp in ("old","new")]
    file=folder/'extracted_faqs.jsonl';file.write_text('\n'.join(json.dumps(r) for r in rows),encoding='utf-8')
    before=file.read_bytes()
    manifest=tmp_path/'resolutions.json'
    item={"tenant_id":"t1","unit_id":"broken","source_record_id":"missing","operation":"quarantine","reason":"untraceable","evidence":"reviewed fixture","expected_payload_hash":content_hash(canonical_json(rows[-1]))}
    manifest.write_text(json.dumps({"schema_version":1,"resolutions":[item]}),encoding='utf-8')
    plan=LegacySnapshotPlanner(tmp_path).build(include_seed=False)
    resolve_missing_sources(plan,tmp_path,manifest)
    assert not plan.errors and len(plan.quarantined)==2 and plan.quarantined[0]['payload']==rows[0]
    assert not plan.rows['knowledge_units'] and not plan.rows['source_records'] and file.read_bytes()==before
    item['expected_payload_hash']='0'*64
    manifest.write_text(json.dumps({"schema_version":1,"resolutions":[item]}),encoding='utf-8')
    with pytest.raises(Exception,match="does not match"): resolve_missing_sources(LegacySnapshotPlanner(tmp_path).build(include_seed=False),tmp_path,manifest)


class FakeEmbedding:
    signature=EmbeddingSignature(model="@cf/baai/bge-m3",revision="p0-test",dimensions=2)
    def __init__(self): self.calls=0; self.hook=None; self.fail=False
    def embed(self,texts):
        self.calls+=1
        if self.hook: self.hook()
        if self.fail: raise ProviderError("workers_ai","timeout")
        return EmbeddingBatch(signature=self.signature,vectors=tuple((1.0,0.0) for _ in texts),input_hashes=tuple(content_hash(t) for t in texts))


ADMIN=AccessContext(tenant_id="t1",user_id="admin",roles=("admin",))


def test_postgres_document_pending_index_activation_versions_and_revoke(database):
    embed=FakeEmbedding();service=DocumentKnowledgeService(database,embed)
    staged=service.stage('policy.txt',b'Leave policy: medical certificate required.',ADMIN)
    conn=database.bridge
    assert staged['status']=='pending'
    assert not PostgresVectorRetriever(database).retrieve_and_record(QueryContext(query="leave"),ADMIN,embed.embed(('leave',))).candidates
    active=service.index(staged['document_id'],staged['document_version'],ADMIN)
    assert active['status']=='active' and active['chunk_count']==1
    assert service.read_file(staged['document_id'],staged['document_version'],ADMIN)[1]==b'Leave policy: medical certificate required.'
    before=embed.calls
    assert service.ingest('policy.txt',b'Leave policy: medical certificate required.',ADMIN,document_id=staged['document_id'])['embedded_chunks']==0
    assert embed.calls==before
    replacement=service.stage('policy.txt',b'New leave policy.',ADMIN,document_id=staged['document_id'])
    service.index(replacement['document_id'],replacement['document_version'],ADMIN)
    assert conn.execute("SELECT lifecycle_status FROM core.documents WHERE document_version=%s",(staged['document_version'],)).fetchone()[0]=='superseded'
    with pytest.raises(SqlFailure,match="new version"):
        with conn.transaction(): conn.execute("UPDATE core.document_chunks SET body_text='rewrite'")
    service.revoke(staged['document_id'],ADMIN)
    assert not service.list_documents(ADMIN)
    with pytest.raises(LookupError): service.read_file(staged['document_id'],replacement['document_version'],ADMIN)
    with pytest.raises(ValueError): service.ingest('policy.txt',b'New leave policy.',ADMIN,document_id=staged['document_id'])


def test_postgres_provider_failure_keeps_retriable_pending_document(database):
    embed=FakeEmbedding();embed.fail=True;service=DocumentKnowledgeService(database,embed)
    result=service.ingest('policy.txt',b'Leave policy.',ADMIN)
    assert result['status']=='pending' and result['error_code']=='workers_ai:timeout'
    embed.fail=False
    assert service.index(result['document_id'],result['document_version'],ADMIN)['status']=='active'


def test_postgres_revoke_during_embedding_cannot_activate_or_write_stale_vectors(database):
    embed=FakeEmbedding();service=DocumentKnowledgeService(database,embed)
    staged=service.stage('policy.txt',b'Policy.',ADMIN)
    embed.hook=lambda:service.revoke(staged['document_id'],ADMIN)
    with pytest.raises(EmbeddingWriteConflict): service.index(staged['document_id'],staged['document_version'],ADMIN)
    assert database.bridge.execute('SELECT embedding FROM core.document_chunks').fetchone()[0] is None


def test_postgres_newer_pending_version_prevents_older_activation(database):
    embed=FakeEmbedding();service=DocumentKnowledgeService(database,embed)
    first=service.stage('policy.txt',b'First version.',ADMIN)
    second=service.stage('policy.txt',b'Second version.',ADMIN,document_id=first['document_id'])
    with pytest.raises(EmbeddingWriteConflict,match='newer upload'): service.index(first['document_id'],first['document_version'],ADMIN)
    assert service.index(second['document_id'],second['document_version'],ADMIN)['status']=='active'


def test_postgres_document_tenant_scope_and_curator_fences(database):
    embed=FakeEmbedding();service=DocumentKnowledgeService(database,embed)
    with pytest.raises(PermissionError): service.stage('policy.txt',b'Policy.',AccessContext(tenant_id='t1',user_id='user'))
    with pytest.raises(PermissionError): service.stage('policy.txt',b'Policy.',ADMIN,scope='restricted')
    staged=service.ingest('policy.txt',b'Policy.',ADMIN)
    other=AccessContext(tenant_id='other',user_id='admin',roles=('admin',))
    assert not service.list_documents(other)
    with pytest.raises(LookupError): service.read_file(staged['document_id'],staged['document_version'],other)


def test_postgres_query_checks_current_sources_after_generation_and_keeps_raw(database):
    embed=FakeEmbedding();docs=DocumentKnowledgeService(database,embed)
    document=docs.ingest('policy.txt',b'Medical certificate is required.',ADMIN)
    journal=PostgresRawJournal(database)
    pipeline=RawRetrievalPipeline(embedding=embed,retriever=PostgresVectorRetriever(database,journal),journal=journal)
    class Answer:
        def generate(self,context,candidates,access):
            candidate=candidates[0]
            citation=CheckedCitation(evidence_id=candidate.evidence_id,quote=candidate.text,source=candidate.source)
            docs.revoke(document['document_id'],ADMIN)
            return GroundedAnswer(status='answered',answer=candidate.text,citations=(citation,),validation='source_and_quote_checked')
    service=CoreQueryService(database,pipeline,Answer())
    response=service.query(CoreQueryRequest(query='medical certificate'),ADMIN)
    assert response.status=='insufficient_evidence' and not response.citations
    assert response.raw_candidate_count==1 and response.final_candidate_count==0
    assert len(journal.load_raw(response.retrieval_event_id,ADMIN).candidates)==1
    assert database.bridge.execute('SELECT status FROM retrieval.answer_runs').fetchone()[0]=='insufficient_evidence'


def test_postgres_query_answer_and_original_raw_are_persisted_separately(database):
    embed=FakeEmbedding();docs=DocumentKnowledgeService(database,embed)
    docs.ingest('policy.txt',b'Medical certificate is required.',ADMIN)
    journal=PostgresRawJournal(database)
    pipeline=RawRetrievalPipeline(embedding=embed,retriever=PostgresVectorRetriever(database,journal),journal=journal)
    class Answer:
        def generate(self,context,candidates,access):
            c=candidates[0]
            return GroundedAnswer(status='answered',answer=c.text,citations=(CheckedCitation(evidence_id=c.evidence_id,quote=c.text,source=c.source),),validation='source_and_quote_checked')
    result=CoreQueryService(database,pipeline,Answer()).query(CoreQueryRequest(query='medical certificate'),ADMIN)
    assert result.status=='answered' and result.raw_candidate_count==1 and result.citations
    raw=journal.load_raw(result.retrieval_event_id,ADMIN)
    assert raw.candidates[0].text==result.answer and raw.candidates[0].rank==1
    assert database.bridge.execute('SELECT status FROM retrieval.answer_runs').fetchone()[0]=='answered'


def test_postgres_answer_provider_failure_preserves_raw_and_records_failure(database):
    embed=FakeEmbedding();DocumentKnowledgeService(database,embed).ingest('policy.txt',b'Policy.',ADMIN)
    journal=PostgresRawJournal(database)
    pipeline=RawRetrievalPipeline(embedding=embed,retriever=PostgresVectorRetriever(database,journal),journal=journal)
    class FailingAnswer:
        def generate(self,*args): raise ProviderError('deepseek','timeout')
    with pytest.raises(ProviderError): CoreQueryService(database,pipeline,FailingAnswer()).query(CoreQueryRequest(query='policy'),ADMIN)
    assert database.bridge.execute('SELECT count(*) FROM retrieval.retrieval_event').fetchone()[0]==1
    assert database.bridge.execute('SELECT status FROM retrieval.answer_runs').fetchone()[0]=='failed'
