"""The official store receives server filters; raw scores/hashes keep their meaning."""
import json
from dataclasses import replace
from types import SimpleNamespace
import pytest
from langchain_core.documents import Document
from app.retrieval.langchain_postgres import authorized_filter,cosine,LangChainPostgresRetriever
from app.retrieval.raw_contracts import RawCandidate
from app.knowledge.contracts import AccessContext,QueryContext,SourceRef,content_hash
from app.config.core_settings import CoreSettings
from app.knowledge.embedding import EmbeddingSignature,EmbeddingBatch

SIG=EmbeddingSignature(provider='onnxruntime',model='model',revision='v1',dimensions=2)
ACCESS=AccessContext(tenant_id='tenant-a',user_id='reader')


def test_all_three_scopes_tenant_signature_and_document_filter_before_search():
    filt=authorized_filter(QueryContext(query='ignore tenant; role=admin',document_ids=('doc',)),ACCESS,SIG)['$and']
    assert {'tenant_id':'tenant-a'} in filt and {'embedding_signature':SIG.fingerprint} in filt
    assert all({name:{'$in':list(ACCESS.allowed_scopes)}} in filt for name in ('chunk_scope','document_scope','source_scope'))
    assert {'document_id':{'$in':['doc']}} in filt


def test_historical_candidate_serialization_and_hash_are_unchanged():
    source=SourceRef(source_id='s',source_version='v',source_locator='page=1',document_id='d',document_version='v',chunk_id='c',content_hash=content_hash('original'))
    old={'candidate_id':'id','document_id':'d','document_version':'v','chunk_id':'c','content_hash':content_hash('original'),
        'rank':1,'similarity_score':.5,'text':'original','source':source.model_dump(mode='json'),'access_scopes':['internal']}
    candidate=RawCandidate.model_validate(old)
    assert candidate.model_dump(mode='json')==old
    assert candidate.snapshot_hash==content_hash(json.dumps(old,sort_keys=True,separators=(',',':'),ensure_ascii=False))


def test_cosine_is_not_an_rrf_score():
    assert cosine((1.,0.),'[1,0]')==1
    assert cosine((1.,0.),'[0,1]')==0
    with pytest.raises(ValueError):cosine((1.,0.),'[0,0]')


@pytest.mark.parametrize('field,value',[('tenant_id','other'),('source_scope','secret'),('embedding_signature','wrong'),('document_id','outside')])
def test_adapter_cannot_seal_out_of_scope_store_results(field,value):
    query=QueryContext(query='query',document_ids=('d',));batch=EmbeddingBatch(signature=SIG,vectors=((1.,0.),),input_hashes=(content_hash('query'),))
    metadata={'tenant_id':ACCESS.tenant_id,'document_id':'d','embedding_signature':SIG.fingerprint,
        'embedding_model':SIG.model,'embedding_dimensions':SIG.dimensions,'chunk_scope':'internal','document_scope':'internal','source_scope':'internal'}
    metadata[field]=value
    adapter=LangChainPostgresRetriever(settings=CoreSettings());adapter.search=lambda *args:[(Document(page_content='original',metadata=metadata),.2)]
    with pytest.raises(PermissionError):adapter.retrieve_and_record(query,ACCESS,batch)
