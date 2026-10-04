"""Official PGVectorStore handles search/fusion; Orion seals facts and provenance."""
import asyncio
import json
import math
from langchain_core.embeddings import Embeddings
from langchain_postgres import PGEngine,PGVectorStore
from langchain_postgres.v2.hybrid_search_config import HybridSearchConfig,reciprocal_rank_fusion
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool
from sqlalchemy.exc import SQLAlchemyError
from app.config.core_settings import CoreSettings
from app.config.runtime_versions import runtime_versions
from app.knowledge.postgres import PostgresDatabase,DatabaseUnavailable
from app.knowledge.contracts import content_hash,SourceRef
from app.knowledge.embedding import normalized_vector
from app.retrieval.raw_contracts import RawCandidate,RawRetrievalEvent,RawRetrievalRecord
from app.retrieval.raw_journal import PostgresRawJournal

METADATA=['tenant_id','document_id','document_version','chunk_id','content_hash','source_locator',
    'source_record_id','source_version','chunk_scope','document_scope','source_scope',
    'embedding_signature','embedding_model','embedding_dimensions','vector_values','business_domain','document_type','title','filename']


class EmbeddingAdapter(Embeddings):
    def __init__(self,provider):self.provider=provider
    def embed_documents(self,texts):return [list(vector) for vector in self.provider.embed(tuple(texts)).vectors]
    def embed_query(self,text):return list(self.provider.embed_query(text).vectors[0])


class PrecomputedEmbedding(Embeddings):
    """By-vector queries must never accidentally re-embed with an unrelated model."""
    def embed_query(self,text):raise RuntimeError('Supply the recorded query embedding')
    def embed_documents(self,texts):raise RuntimeError('Ingestion owns embedding writes')


def authorized_filter(context,access,signature):
    clauses=[{'tenant_id':access.tenant_id},{'embedding_signature':signature.fingerprint},
        {'embedding_model':signature.model},{'embedding_dimensions':signature.dimensions}]
    clauses.extend({name:{'$in':list(access.allowed_scopes)}} for name in ('chunk_scope','document_scope','source_scope'))
    if context.document_ids:clauses.append({'document_id':{'$in':list(context.document_ids)}})
    return {'$and':clauses}


def cosine(query,stored):
    vector=tuple(json.loads(stored))
    normalized_vector(vector,len(query))
    return sum(a*b for a,b in zip(query,vector))/math.sqrt(sum(a*a for a in query)*sum(b*b for b in vector))


class LangChainPostgresRetriever:
    def __init__(self,database=None,journal=None,settings=None):
        self.settings=settings or CoreSettings()
        self.database=database or PostgresDatabase(self.settings)
        self.journal=journal or PostgresRawJournal(self.database)

    def search(self,context,access,batch,top_k):
        url=make_url(self.settings.require_database_url()).set(drivername='postgresql+asyncpg')
        engine=PGEngine.from_connection_string(url,hide_parameters=True,echo=False,poolclass=NullPool,
            connect_args={'timeout':self.settings.database_connect_timeout_seconds})
        try:
            store=PGVectorStore.create_sync(engine,PrecomputedEmbedding(),table_name='retrieval_chunks',schema_name='core',
                id_column='retrieval_id',content_column='body_text',embedding_column='embedding',metadata_columns=METADATA)
            kwargs={}
            if self.settings.retrieval_mode=='hybrid':
                kwargs['hybrid_search_config']=HybridSearchConfig(tsv_column='body_tsv',tsv_lang='pg_catalog.simple',
                    primary_top_k=top_k,secondary_top_k=top_k,fts_query=context.query,
                    fusion_function=reciprocal_rank_fusion,fusion_function_parameters={'rrf_k':60})
            return store.similarity_search_with_score_by_vector(list(batch.vectors[0]),k=top_k,
                filter=authorized_filter(context,access,batch.signature),**kwargs)
        except SQLAlchemyError:raise DatabaseUnavailable('PGVectorStore query failed') from None
        finally:asyncio.run(engine.close())

    def retrieve_and_record(self,context,access,embedding,top_k=20):
        if isinstance(top_k,bool) or not 1<=top_k<=100:raise ValueError('Raw top_k must be between 1 and 100')
        if context.entities:raise ValueError('Resolve entity document scope before retrieval')
        if len(embedding.vectors)!=1 or embedding.input_hashes!=(content_hash(context.query),):raise ValueError('Query embedding mismatch')
        normalized_vector(embedding.vectors[0],embedding.signature.dimensions)
        rows=self.search(context,access,embedding,top_k)
        hybrid=self.settings.retrieval_mode=='hybrid'
        method='pgvector_hybrid_rrf' if hybrid else 'pgvector_exact_cosine'
        candidates=[]
        for rank,(doc,score) in enumerate(rows,1):
            metadata=doc.metadata
            # This is a second validation boundary, not a substitute for SQL filters.
            if (metadata['tenant_id']!=access.tenant_id or metadata['embedding_signature']!=embedding.signature.fingerprint
                or metadata['embedding_model']!=embedding.signature.model or metadata['embedding_dimensions']!=embedding.signature.dimensions
                or any(metadata[name] not in access.allowed_scopes for name in ('chunk_scope','document_scope','source_scope'))
                or (context.document_ids and metadata['document_id'] not in context.document_ids)):
                raise PermissionError('Vector store returned out-of-scope data')
            similarity=cosine(embedding.vectors[0],metadata['vector_values']) if hybrid else 1-float(score)
            source=SourceRef(source_id=metadata['source_record_id'],source_version=metadata['source_version'],
                source_locator=metadata['source_locator'],document_id=metadata['document_id'],
                document_version=metadata['document_version'],chunk_id=metadata['chunk_id'],content_hash=metadata['content_hash'])
            candidates.append(RawCandidate(document_id=metadata['document_id'],document_version=metadata['document_version'],
                chunk_id=metadata['chunk_id'],content_hash=metadata['content_hash'],rank=rank,similarity_score=similarity,
                text=doc.page_content,source=source,access_scopes=tuple(dict.fromkeys(metadata[n] for n in ('chunk_scope','document_scope','source_scope'))),
                **({'retrieval_method':method,'retrieval_scores':{'vector_similarity':similarity,'rrf_score':float(score)}} if hybrid else {})))
        event=RawRetrievalEvent(tenant_id=access.tenant_id,user_id=access.user_id,query=context.query,
            query_hash=content_hash(context.query),embedding_configuration=embedding.signature,query_vector=embedding.vectors[0],
            document_ids=context.document_ids,allowed_scopes=access.allowed_scopes,top_k=top_k,candidate_count=len(candidates),
            retrieval_method=method,runtime_versions=runtime_versions(embedding.signature,top_k,retrieval_method=method,retrieval_adapter='langchain_postgres'))
        record=RawRetrievalRecord(event=event,candidates=tuple(candidates))
        with self.database.connection() as connection:
            with connection.transaction():self.journal.record_raw(connection,record,access)
        return record
