"""Corpus identities, reproducible manifests, guarded writes and resumable indexing."""

import shutil

import pytest

from app.knowledge.benchmark_ingestion import CorpusPlan, CorpusIngestion, CorpusRepository
from app.knowledge.contracts import AccessContext, QueryContext
from app.knowledge.document_ingestion import DocumentKnowledgeService
from app.retrieval.postgres_vector import PostgresVectorRetriever, EmbeddingWriteConflict
from test_p0_core import FakeEmbedding
from test_raw_postgres_integration import database, SqlFailure

ACCESS=AccessContext(tenant_id='bench-test',user_id='curator',roles=('admin',))


def write_corpus(root):
    root.mkdir(parents=True,exist_ok=True)
    first=root/('dsid_'+'a'*32+'__medical-policy.txt')
    first.write_bytes(b'Medical policy\n\nLiteral escape: \\n. '+b'certificate required. '*50)
    folder=root/'team';folder.mkdir()
    second=folder/('dsid_'+'b'*32+'__oncall-policy.txt')
    second.write_bytes(b'Oncall policy\n\nContact the incident commander.')
    return root


def test_corpus_manifest_is_portable_preserves_original_ids_and_literal_escapes(tmp_path):
    root=write_corpus(tmp_path/'corpus');plan=CorpusPlan.build(root,ACCESS.tenant_id)
    moved=tmp_path/'moved';shutil.copytree(root,moved)
    other=CorpusPlan.build(moved,ACCESS.tenant_id)
    assert plan.snapshot_hash==other.snapshot_hash
    assert plan.documents[0].external_id=='dsid_'+'a'*32
    assert plan.documents[0].document_id=='erag-confluence:dsid_'+'a'*32
    assert b'\\n' in plan.read(plan.documents[0])
    assert plan.origin('team/a.txt','dsid_x','title').source_locator.endswith('team/a.txt')
    assert 'answer' not in plan.manifest and 'question' not in plan.manifest
    with pytest.raises(PermissionError): CorpusRepository.authorize(plan,AccessContext(tenant_id='other',user_id='admin',roles=('admin',)))


@pytest.mark.parametrize('problem',['duplicate_id','unsupported_name','bad_utf8','empty'])
def test_invalid_corpus_is_blocked_before_ingestion(tmp_path,problem):
    root=write_corpus(tmp_path/'corpus')
    if problem=='duplicate_id': (root/'team'/('dsid_'+'a'*32+'__duplicate.txt')).write_bytes(b'duplicate')
    elif problem=='unsupported_name': (root/'questions.jsonl').write_text('{"answer":"not corpus"}',encoding='utf-8')
    elif problem=='bad_utf8': next(root.glob('*.txt')).write_bytes(b'\xff\xff')
    else: next(root.glob('*.txt')).write_bytes(b'')
    with pytest.raises((ValueError,UnicodeError)): CorpusPlan.build(root,ACCESS.tenant_id)


def test_changed_file_cannot_be_staged_under_pinned_manifest(database,tmp_path):
    root=write_corpus(tmp_path/'corpus');plan=CorpusPlan.build(root,ACCESS.tenant_id)
    next(root.glob('*.txt')).write_bytes(b'changed')
    with pytest.raises(ValueError,match='changed after'): CorpusIngestion(database,FakeEmbedding()).stage(plan,ACCESS)
    assert database.bridge.execute('SELECT count(*) FROM core.documents').fetchone()[0]==0


def test_corpus_stage_partial_index_resume_activation_and_repeat_are_idempotent(database,tmp_path):
    plan=CorpusPlan.build(write_corpus(tmp_path/'corpus'),ACCESS.tenant_id)
    embedding=FakeEmbedding();service=CorpusIngestion(database,embedding)
    service.stage(plan,ACCESS)
    service.stage(plan,ACCESS)
    assert service.repository.status(plan,ACCESS,embedding.signature)['linked_documents']==2
    raw=PostgresVectorRetriever(database).retrieve_and_record(QueryContext(query='certificate'),ACCESS,embedding.embed(('certificate',)))
    assert not raw.candidates
    partial=service.index(plan,ACCESS,workers=1,batch_size=1,max_batches=1)
    assert partial['status']=='partial' and partial['ready_vectors']==1 and partial['active_documents']==0
    complete=service.index(plan,ACCESS,workers=1)
    assert complete['status']=='complete' and complete['ready_vectors']==plan.chunk_count and complete['active_documents']==2
    assert complete['vectors_written']==plan.chunk_count-1
    calls=embedding.calls
    repeated=service.index(plan,ACCESS,workers=1)
    assert repeated['vectors_written']==0 and embedding.calls==calls
    assert database.bridge.execute('SELECT count(*) FROM core.documents').fetchone()[0]==2
    assert database.bridge.execute('SELECT count(*) FROM core.dataset_snapshot_documents').fetchone()[0]==2
    document=plan.documents[0]
    assert service.documents.read_file(document.document_id,document.document_version,ACCESS)[1]==plan.read(document)
    raw=PostgresVectorRetriever(database).retrieve_and_record(QueryContext(query='certificate'),ACCESS,embedding.embed(('certificate',)))
    assert len(raw.candidates)==plan.chunk_count
    assert all(c.source.source_locator.startswith('benchmark://EnterpriseRAG-Bench/confluence/') for c in raw.candidates)
    source=database.bridge.execute('SELECT source_system,external_id,raw_content FROM core.source_records ORDER BY external_id').fetchone()
    assert source[0]=='enterprise_rag_bench.confluence' and source[1]==document.external_id and '\\n' in source[2]
    with pytest.raises(SqlFailure,match='immutable'):
        with database.bridge.transaction(): database.bridge.execute("UPDATE core.dataset_snapshots SET manifest='{}'")


@pytest.mark.parametrize('change',['revoke','scope','new_head'])
def test_corpus_write_rechecks_permissions_and_current_version_after_inference(database,tmp_path,change):
    plan=CorpusPlan.build(write_corpus(tmp_path/'corpus'),ACCESS.tenant_id)
    embedding=FakeEmbedding();service=CorpusIngestion(database,embedding);service.stage(plan,ACCESS)
    def changed():
        if change=='revoke': database.bridge.execute("UPDATE core.source_records SET lifecycle_status='revoked'")
        elif change=='scope': database.bridge.execute("UPDATE core.source_records SET access_scope='restricted'")
        else:
            d=plan.documents[0]
            service.documents.stage(d.filename,b'New corpus version.',ACCESS,document_id=d.document_id,
                origin=plan.origin(d.relative_path,d.external_id,'New title'))
    embedding.hook=changed
    with pytest.raises(EmbeddingWriteConflict): service.index(plan,ACCESS,workers=1)
    assert database.bridge.execute('SELECT count(*) FROM core.document_chunks WHERE embedding IS NOT NULL').fetchone()[0]==0


def test_additional_chunk_cannot_silently_change_the_corpus_baseline(database,tmp_path):
    plan=CorpusPlan.build(write_corpus(tmp_path/'corpus'),ACCESS.tenant_id)
    service=CorpusIngestion(database,FakeEmbedding());service.stage(plan,ACCESS)
    database.bridge.execute("""INSERT INTO core.document_chunks
        (tenant_id,chunk_id,document_id,document_version,chunk_index,body_text,content_hash,source_locator,access_scope,lifecycle_status)
        SELECT tenant_id,'extra',document_id,document_version,999,body_text,content_hash,source_locator,access_scope,lifecycle_status
        FROM core.document_chunks ORDER BY chunk_id LIMIT 1""")
    from app.knowledge.postgres import MigrationError
    with pytest.raises(MigrationError,match='verify every'): service.index(plan,ACCESS,workers=1)
