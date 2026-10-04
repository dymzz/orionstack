"""P0-3/4 orchestration: exact queries, sealed raw facts and bounded checked output."""

import pytest
import json

from app.config.core_settings import CoreSettings
from app.decision.grounded_answer import CheckedCitation, GroundedAnswer
from app.decision.retrieval_processors import RuleRetrievalProcessor
from app.knowledge.contracts import content_hash
from app.knowledge.document_ingestion import DocumentKnowledgeService
from app.knowledge.embedding import EmbeddingBatch, EmbeddingSignature
from app.providers.http import ProviderError
from app.retrieval.postgres_vector import PostgresVectorRetriever
from app.retrieval.raw_journal import PostgresRawJournal
from app.retrieval.raw_pipeline import RawRetrievalPipeline
from app.services.core_query_service import CoreQueryRequest, CoreQueryService
from test_p0_core import ADMIN, FakeEmbedding
from test_raw_postgres_integration import database


class QueryEmbedding(FakeEmbedding):
    signature = EmbeddingSignature(provider='onnxruntime',model='Qwen/Qwen3-Embedding-0.6B',
        revision='acceptance-test',dimensions=2,preprocessing='qwen3_last_token_query_instruction_v1')

    def __init__(self):
        super().__init__()
        self.queries = []

    def embed_query(self, text):
        self.queries.append(text)
        return EmbeddingBatch(signature=self.signature,vectors=((1.0,0.0),),input_hashes=(content_hash(text),))


def setup(database, *, processors=(), stage=True):
    embedding = QueryEmbedding()
    documents = DocumentKnowledgeService(database,embedding)
    document = documents.ingest('policy.txt',b'Medical certificate is required.',ADMIN) if stage else None
    journal = PostgresRawJournal(database)
    pipeline = RawRetrievalPipeline(embedding=embedding,retriever=PostgresVectorRetriever(database,journal),
        journal=journal,processors=processors)
    return embedding, documents, document, journal, pipeline


def test_exact_query_uses_query_encoder_and_raw_is_sealed_before_answer(database):
    embedding, _, _, journal, pipeline = setup(database)
    query = ' \n medical  certificate\t policy?\n '
    class Answer:
        def generate(self, context, candidates, access):
            row = database.bridge.execute('SELECT id,query,query_hash,embedding_configuration FROM retrieval.retrieval_event').fetchone()
            assert row[1:3] == (query,content_hash(query))
            assert row[3]['provider'] == 'onnxruntime'
            raw = journal.load_raw(row[0],access)
            assert len(raw.candidates) == 1
            candidate = candidates[0]
            return GroundedAnswer(status='answered',answer=candidate.text,
                citations=(CheckedCitation(evidence_id=candidate.evidence_id,quote=candidate.text,source=candidate.source),))
    answer = CoreQueryService(database,pipeline,Answer()).query(CoreQueryRequest(query=query),ADMIN)
    assert embedding.queries == [query] and answer.validation == 'source_and_quote_checked'
    raw = journal.load_raw(answer.retrieval_event_id,ADMIN)
    assert raw.event.query == query and raw.event.embedding_configuration == embedding.signature
    persisted = database.bridge.execute('SELECT response FROM retrieval.answer_runs').fetchone()[0]
    assert persisted == answer.model_dump(mode='json')


@pytest.mark.parametrize('reason',['no_recall','processor_filtered','source_revoked'])
def test_no_accessible_evidence_never_invokes_answer_model_but_keeps_raw(database,reason):
    processors = (RuleRetrievalProcessor(lambda query,candidate:False,'exclude-all-v1'),) if reason=='processor_filtered' else ()
    _, documents, document, journal, pipeline = setup(database,processors=processors,stage=reason!='no_recall')
    if reason=='source_revoked':
        retrieve = pipeline.retrieve
        def revoke_after_recall(*args,**kwargs):
            result = retrieve(*args,**kwargs)
            documents.revoke(document['document_id'],ADMIN)
            return result
        pipeline.retrieve = revoke_after_recall
    class ForbiddenAnswer:
        def generate(self,*args): pytest.fail('No accessible evidence must not reach an answer provider')
    result = CoreQueryService(database,pipeline,ForbiddenAnswer()).query(CoreQueryRequest(query='policy'),ADMIN)
    raw = journal.load_raw(result.retrieval_event_id,ADMIN)
    assert result.status=='insufficient_evidence' and result.validation=='no_verified_answer' and not result.citations
    assert len(raw.candidates)==(0 if reason=='no_recall' else 1)
    assert database.bridge.execute('SELECT status FROM retrieval.answer_runs').fetchone()[0]=='insufficient_evidence'


@pytest.mark.parametrize('payload',[None,'fake-private-provider-output',
    {'status':'answered','answer':'fake-private-provider-output','citations':'malformed'},
    {'status':'insufficient_evidence','answer':'fake-private-provider-output','extra':'forbidden'}])
def test_malformed_answer_adapter_returns_redacted_failure_and_preserves_raw(database,payload):
    _, _, _, journal, pipeline = setup(database)
    class MalformedAnswer:
        def generate(self,*args): return payload
    with pytest.raises(ProviderError,match='invalid_grounded_answer') as caught:
        CoreQueryService(database,pipeline,MalformedAnswer()).query(CoreQueryRequest(query='policy'),ADMIN)
    assert 'fake-private' not in str(caught.value)
    event_id = database.bridge.execute('SELECT id FROM retrieval.retrieval_event').fetchone()[0]
    assert len(journal.load_raw(event_id,ADMIN).candidates)==1
    audit = database.bridge.execute('SELECT status,response FROM retrieval.answer_runs').fetchone()
    assert audit[0]=='failed' and audit[1]['status']=='failed' and audit[1]['error_code']=='deepseek:invalid_grounded_answer'
    feedback=audit[1]['execution_feedback']
    assert feedback['retrieval_event_id']==event_id and feedback['reason']=='unverified_answer'
    assert feedback['model_call']['status']=='unknown' and feedback['model_call']['attempted'] is None
    assert 'fake-private' not in json.dumps(audit[1])


def test_duplicate_checked_excerpts_cannot_be_returned_as_verified_answer(database):
    _, _, _, journal, pipeline = setup(database)
    class DuplicateAnswer:
        def generate(self,context,candidates,access):
            c = candidates[0]
            quote = CheckedCitation(evidence_id=c.evidence_id,quote=c.text,source=c.source)
            return GroundedAnswer(status='answered',answer=c.text+'\n\n'+c.text,citations=(quote,quote))
    result = CoreQueryService(database,pipeline,DuplicateAnswer()).query(CoreQueryRequest(query='policy'),ADMIN)
    assert result.status=='insufficient_evidence' and not result.citations
    assert len(journal.load_raw(result.retrieval_event_id,ADMIN).candidates)==1


def test_copied_model_cannot_bypass_quote_or_citation_bounds(database):
    _, _, _, journal, pipeline = setup(database)
    class CopiedAnswer:
        def generate(self,context,candidates,access):
            c = candidates[0]
            citation = CheckedCitation(evidence_id=c.evidence_id,quote=c.text,source=c.source)
            return GroundedAnswer(status='answered',answer=c.text,citations=(citation,)).model_copy(
                update={'citations':(citation,)*6})
    with pytest.raises(ProviderError,match='invalid_grounded_answer'):
        CoreQueryService(database,pipeline,CopiedAnswer()).query(CoreQueryRequest(query='policy'),ADMIN)
    event_id = database.bridge.execute('SELECT id FROM retrieval.retrieval_event').fetchone()[0]
    assert len(journal.load_raw(event_id,ADMIN).candidates)==1


def test_default_policy_does_not_construct_jev_and_explicit_policy_uses_given_settings(monkeypatch):
    import app.decision.jev as jev
    original = jev.JevClient
    monkeypatch.setattr(jev,'JevClient',lambda *args:pytest.fail('Default core query must not require Jev'))
    default = CoreQueryService(settings=CoreSettings(query_use_jev=False,typesafe_api_key=''))
    assert default.pipeline.processors==()
    monkeypatch.setattr(jev,'JevClient',original)
    configured = CoreSettings(query_use_jev=True,jev_model='custom-jev',jev_api_base='https://custom.example/v1',
        typesafe_api_key='fake-test-key')
    enabled = CoreQueryService(settings=configured)
    assert enabled.pipeline.processors[0].client.settings is configured
