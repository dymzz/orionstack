"""Pinned Confluence corpus ingestion, independent of query processors and labels."""

from collections import deque
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, as_completed, wait
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from functools import cached_property
import json
from pathlib import Path
import re
import threading
from urllib.parse import quote

import httpx
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.knowledge.contracts import AccessContext, content_hash
from app.knowledge.document_ingestion import DocumentKnowledgeService, DocumentOrigin, document_version, require_curator
from app.knowledge.embedding import WorkersAIEmbeddingClient, create_embedding_client, normalized_vector
from app.knowledge.legacy_migration import canonical_json
from app.knowledge.postgres import MigrationError, PostgresDatabase
from app.retrieval.postgres_vector import EmbeddingWriteConflict, vector_literal
from app.services.chunk_service import ChunkService
from app.services.document_parser import DocumentParser

DATASET_ID = "EnterpriseRAG-Bench/confluence"


@dataclass(frozen=True)
class CorpusDocument:
    external_id: str
    relative_path: str
    filename: str
    title: str
    content_hash: str
    size_bytes: int
    text_length: int
    chunk_count: int
    document_id: str
    document_version: str


@dataclass(frozen=True)
class CorpusPlan:
    root: Path
    tenant_id: str
    scope: str
    dataset_version: str
    documents: tuple[CorpusDocument, ...]

    def origin(self, relative_path, external_id, title):
        return DocumentOrigin(source_id="enterprise-rag-bench:confluence:"+external_id,
            source_system="enterprise_rag_bench.confluence",external_id=external_id,
            source_locator="benchmark://EnterpriseRAG-Bench/confluence/"+quote(relative_path,safe="/"),title=title,
            metadata={"dataset_id":DATASET_ID,"dataset_version":self.dataset_version,
                      "relative_path":relative_path,"original_dsid":external_id})

    @classmethod
    def build(cls, root: Path, tenant_id="enterprise-rag-bench", scope="internal", dataset_version="v1.0.0"):
        root=root.resolve()
        if not root.is_dir() or not tenant_id.strip() or not scope.strip():
            raise ValueError("An existing corpus directory, tenant and scope are required")
        plan=cls(root,tenant_id,scope,dataset_version,())
        documents=[]; seen=set()
        for file in sorted((p for p in root.rglob('*') if p.is_file()),key=lambda p:p.relative_to(root).as_posix()):
            if not file.resolve().is_relative_to(root):
                raise ValueError("Corpus file escapes the selected directory")
            match=re.fullmatch(r'(dsid_[0-9a-f]{32})__(.+)\.txt',file.name)
            if not match or match[1] in seen:
                raise ValueError("Corpus filenames must contain unique original dsid identifiers")
            seen.add(match[1]);data=file.read_bytes()
            if not data or len(data)>10*1024*1024 or len(file.name)>240:
                raise ValueError("Corpus file exceeds document ingestion limits")
            # The corpus is UTF-8; do not silently reinterpret bytes or literal backslash-n sequences.
            data.decode('utf-8')
            text=DocumentParser().parse(filename=file.name,data=data)
            chunks=ChunkService().split(text)
            if not chunks or len(text)>100_000:
                raise ValueError("Corpus parsed text exceeds document ingestion limits")
            relative=file.relative_to(root).as_posix(); title=text.splitlines()[0].strip()[:1024]
            origin=plan.origin(relative,match[1],title)
            documents.append(CorpusDocument(match[1],relative,file.name,title,content_hash(data),len(data),
                len(text),len(chunks),"erag-confluence:"+match[1],document_version(data,origin)))
        if not documents:
            raise ValueError("Corpus directory contains no documents")
        return cls(root,tenant_id,scope,dataset_version,tuple(documents))

    @cached_property
    def manifest(self):
        return {"schema_version":1,"dataset_id":DATASET_ID,"dataset_version":self.dataset_version,
                "tenant_id":self.tenant_id,"access_scope":self.scope,"parser":"v1",
                "chunking":"chars500-overlap80-v1","provenance_policy":"original_dsid_path_v1",
                "documents":[asdict(d) for d in self.documents]}

    @cached_property
    def snapshot_hash(self): return content_hash(canonical_json(self.manifest))

    @cached_property
    def chunk_count(self): return sum(d.chunk_count for d in self.documents)

    def read(self, document):
        path=(self.root/document.relative_path).resolve()
        if not path.is_relative_to(self.root): raise ValueError("Corpus file escapes the selected directory")
        data=path.read_bytes()
        if content_hash(data)!=document.content_hash:
            raise ValueError("Corpus file changed after the manifest was pinned")
        return data


class CorpusRepository:
    def __init__(self, database=None): self.database=database or PostgresDatabase()

    @staticmethod
    def authorize(plan,access):
        require_curator(access,plan.scope)
        if access.tenant_id!=plan.tenant_id: raise PermissionError("Corpus tenant does not match the principal")

    @contextmanager
    def maintenance_lock(self,plan,access):
        self.authorize(plan,access)
        key=plan.tenant_id+":dataset:"+DATASET_ID
        with self.database.connection() as connection:
            if not connection.execute('SELECT pg_try_advisory_lock(hashtext(%s))',(key,)).fetchone()[0]:
                raise EmbeddingWriteConflict("Another process is ingesting this corpus")
            try: yield
            finally: connection.execute('SELECT pg_advisory_unlock(hashtext(%s))',(key,))

    def register(self,plan,access):
        self.authorize(plan,access)
        with self.database.connection() as connection:
            with connection.transaction():
                connection.execute("""INSERT INTO core.dataset_snapshots
                    (tenant_id,dataset_id,snapshot_hash,manifest,document_count,chunk_count)
                    VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
                    (plan.tenant_id,DATASET_ID,plan.snapshot_hash,Jsonb(plan.manifest),len(plan.documents),plan.chunk_count))
                row=connection.execute('SELECT manifest FROM core.dataset_snapshots WHERE tenant_id=%s AND dataset_id=%s AND snapshot_hash=%s',
                                       (plan.tenant_id,DATASET_ID,plan.snapshot_hash)).fetchone()
                if row[0]!=plan.manifest: raise MigrationError("Stored corpus manifest conflicts with this snapshot")

    def link(self,plan,document,access):
        self.authorize(plan,access)
        values=(plan.tenant_id,DATASET_ID,plan.snapshot_hash,document.external_id,document.relative_path,
                document.document_id,document.document_version,document.content_hash,document.chunk_count)
        with self.database.connection() as connection:
            with connection.transaction():
                connection.execute("""INSERT INTO core.dataset_snapshot_documents
                    (tenant_id,dataset_id,snapshot_hash,external_id,relative_path,document_id,document_version,content_hash,chunk_count)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING""",values)
                row=connection.execute("""SELECT tenant_id,dataset_id,snapshot_hash,external_id,relative_path,
                    document_id,document_version,content_hash,chunk_count FROM core.dataset_snapshot_documents
                    WHERE tenant_id=%s AND dataset_id=%s AND snapshot_hash=%s AND external_id=%s""",values[:4]).fetchone()
                if tuple(row)!=values: raise MigrationError("Stored corpus member conflicts with the manifest")

    def pending(self,plan,access,signature,limit=256,after=("","",-1)):
        self.authorize(plan,access)
        with self.database.connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                return tuple(cursor.execute("""SELECT c.document_id,c.document_version,c.chunk_index,c.chunk_id,c.body_text,c.content_hash
                    FROM core.dataset_snapshot_documents m JOIN core.document_chunks c USING (tenant_id,document_id,document_version)
                    JOIN core.documents d USING (tenant_id,document_id,document_version)
                    JOIN core.source_records s ON (d.tenant_id,d.source_record_id,d.source_version)=(s.tenant_id,s.source_record_id,s.source_version)
                    JOIN core.document_heads h ON (d.tenant_id,d.document_id,d.document_version)=(h.tenant_id,h.document_id,h.target_version)
                    WHERE m.tenant_id=%s AND m.dataset_id=%s AND m.snapshot_hash=%s
                      AND c.lifecycle_status IN ('pending','active') AND d.lifecycle_status IN ('pending','active') AND s.lifecycle_status IN ('pending','active')
                      AND c.access_scope=ANY(%s::text[]) AND d.access_scope=ANY(%s::text[]) AND s.access_scope=ANY(%s::text[])
                      AND (c.embedding IS NULL OR c.embedding_signature IS DISTINCT FROM %s
                           OR c.embedding_model IS DISTINCT FROM %s OR c.embedding_dimensions IS DISTINCT FROM %s
                           OR c.embedding_content_hash IS DISTINCT FROM c.content_hash)
                      AND (c.document_id,c.document_version,c.chunk_index)>(%s,%s,%s)
                    ORDER BY c.document_id,c.document_version,c.chunk_index LIMIT %s""",
                    (plan.tenant_id,DATASET_ID,plan.snapshot_hash,*([list(access.allowed_scopes)]*3),signature.fingerprint,signature.model,signature.dimensions,*after,limit)).fetchall())

    def save_batch(self,plan,access,chunks,batch):
        self.authorize(plan,access)
        if not chunks or len(chunks)>32 or len(chunks)!=len(batch.vectors) or len(chunks)!=len(batch.input_hashes):
            raise EmbeddingWriteConflict("Embedding batch shape does not match corpus chunks")
        with self.database.connection() as connection:
            with connection.transaction():
                # Same lock order as upload/index/revoke; external inference runs before these locks.
                for identity in sorted({c['document_id'] for c in chunks}):
                    connection.execute('SELECT pg_advisory_xact_lock(hashtext(%s))',(access.tenant_id+':document:'+identity,))
                with connection.cursor(row_factory=dict_row) as cursor:
                    rows=cursor.execute("""SELECT c.chunk_id,c.body_text,c.content_hash,c.document_id,c.document_version
                        FROM core.dataset_snapshot_documents m JOIN core.document_chunks c USING (tenant_id,document_id,document_version)
                        JOIN core.documents d USING (tenant_id,document_id,document_version)
                        JOIN core.source_records s ON (d.tenant_id,d.source_record_id,d.source_version)=(s.tenant_id,s.source_record_id,s.source_version)
                        JOIN core.document_heads h ON (d.tenant_id,d.document_id,d.document_version)=(h.tenant_id,h.document_id,h.target_version)
                        WHERE m.tenant_id=%s AND m.dataset_id=%s AND m.snapshot_hash=%s AND c.chunk_id=ANY(%s::text[])
                          AND c.lifecycle_status IN ('pending','active') AND d.lifecycle_status IN ('pending','active') AND s.lifecycle_status IN ('pending','active')
                          AND c.access_scope=ANY(%s::text[]) AND d.access_scope=ANY(%s::text[]) AND s.access_scope=ANY(%s::text[])
                        ORDER BY c.document_id,c.chunk_id FOR SHARE OF c,d,s,h""",
                        (plan.tenant_id,DATASET_ID,plan.snapshot_hash,[c['chunk_id'] for c in chunks],*([list(access.allowed_scopes)]*3))).fetchall()
                current={r['chunk_id']:r for r in rows}
                if len(current)!=len(chunks): raise EmbeddingWriteConflict("Corpus version, head or permissions changed during inference")
                for chunk,vector,digest in zip(chunks,batch.vectors,batch.input_hashes):
                    row=current.get(chunk['chunk_id'])
                    if (row is None or row['body_text']!=chunk['body_text'] or row['content_hash']!=digest
                            or digest!=chunk['content_hash'] or digest!=content_hash(chunk['body_text']) or row['document_id']!=chunk['document_id']
                            or row['document_version']!=chunk['document_version']):
                        raise EmbeddingWriteConflict("Corpus embedding input does not match pinned content")
                    normalized_vector(vector,batch.signature.dimensions)
                    connection.execute("""UPDATE core.document_chunks SET embedding=%s::vector,embedding_model=%s,
                        embedding_dimensions=%s,embedding_content_hash=%s,embedding_signature=%s
                        WHERE tenant_id=%s AND chunk_id=%s AND document_version=%s""",
                        (vector_literal(vector),batch.signature.model,batch.signature.dimensions,digest,batch.signature.fingerprint,
                         access.tenant_id,chunk['chunk_id'],chunk['document_version']))
        return len(chunks)

    def status(self,plan,access,signature):
        self.authorize(plan,access)
        with self.database.connection() as connection:
            linked,active=connection.execute("""SELECT count(*) AS linked_documents,count(*) FILTER(WHERE d.lifecycle_status='active') AS active_documents
                FROM core.dataset_snapshot_documents m JOIN core.documents d USING(tenant_id,document_id,document_version)
                WHERE m.tenant_id=%s AND m.dataset_id=%s AND m.snapshot_hash=%s""",
                (plan.tenant_id,DATASET_ID,plan.snapshot_hash)).fetchone()
            total,ready=connection.execute("""SELECT count(*) AS stored_chunks,count(*) FILTER(WHERE c.embedding IS NOT NULL AND c.embedding_signature=%s
                  AND c.embedding_model=%s AND c.embedding_dimensions=%s AND c.embedding_content_hash=c.content_hash
                  AND c.lifecycle_status IN ('pending','active') AND d.lifecycle_status IN ('pending','active') AND s.lifecycle_status IN ('pending','active')
                  AND c.access_scope=ANY(%s::text[]) AND d.access_scope=ANY(%s::text[]) AND s.access_scope=ANY(%s::text[])
                  AND h.target_version=d.document_version) AS ready_vectors
                FROM core.dataset_snapshot_documents m JOIN core.document_chunks c USING(tenant_id,document_id,document_version)
                JOIN core.documents d USING(tenant_id,document_id,document_version)
                JOIN core.source_records s ON(d.tenant_id,d.source_record_id,d.source_version)=(s.tenant_id,s.source_record_id,s.source_version)
                LEFT JOIN core.document_heads h ON(d.tenant_id,d.document_id)=(h.tenant_id,h.document_id)
                WHERE m.tenant_id=%s AND m.dataset_id=%s AND m.snapshot_hash=%s""",
                (signature.fingerprint,signature.model,signature.dimensions,*([list(access.allowed_scopes)]*3),plan.tenant_id,DATASET_ID,plan.snapshot_hash)).fetchone()
            invalid=connection.execute("""SELECT count(*) FROM core.dataset_snapshot_documents m
                WHERE m.tenant_id=%s AND m.dataset_id=%s AND m.snapshot_hash=%s AND m.chunk_count<>(
                    SELECT count(*) FROM core.document_chunks c WHERE(c.tenant_id,c.document_id,c.document_version)=(m.tenant_id,m.document_id,m.document_version))""",
                (plan.tenant_id,DATASET_ID,plan.snapshot_hash)).fetchone()[0]
        return {"linked_documents":linked,"active_documents":active,"stored_chunks":total,"ready_vectors":ready,
                "expected_documents":len(plan.documents),"expected_chunks":plan.chunk_count,"invalid_chunk_counts":invalid}


class CorpusIngestion:
    def __init__(self,database=None,embedding=None):
        self.database=database or PostgresDatabase()
        self.embedding=embedding or create_embedding_client(self.database.settings)
        self.repository=CorpusRepository(self.database)
        self.documents=DocumentKnowledgeService(self.database,self.embedding)

    def stage(self,plan,access,progress=lambda event:None):
        self.repository.register(plan,access)
        for number,document in enumerate(plan.documents,1):
            result=self.documents.stage(document.filename,plan.read(document),access,document_id=document.document_id,
                scope=plan.scope,content_type='text/plain',origin=plan.origin(document.relative_path,document.external_id,document.title))
            if result['document_version']!=document.document_version: raise MigrationError("Document version differs from the corpus plan")
            self.repository.link(plan,document,access)
            if number==1 or number%100==0 or number==len(plan.documents):
                progress({"phase":"stage","staged_documents":number,"expected_documents":len(plan.documents)})

    def index(self,plan,access,*,workers=8,batch_size=32,max_batches=None,progress=lambda event:None):
        if not 1<=workers<=16 or not 1<=batch_size<=32 or (max_batches is not None and max_batches<1):
            raise ValueError("Invalid corpus indexing limits")
        signature=self.embedding.signature
        status=self.repository.status(plan,access,signature)
        if status['linked_documents']!=len(plan.documents) or status['invalid_chunk_counts']:
            raise MigrationError("Stage and verify every corpus document before indexing")
        if status['ready_vectors']==plan.chunk_count and status['active_documents']==len(plan.documents):
            return {"status":"complete",**status,"vectors_written":0,"completed_batches":0}
        initial_ready=status['ready_vectors']; completed=0; written=0; after=("","",-1)
        local=threading.local();clients=[];clients_lock=threading.Lock()
        def work(chunks):
            if not hasattr(local,'embedding'):
                if isinstance(self.embedding,WorkersAIEmbeddingClient):
                    client=httpx.Client()
                    with clients_lock: clients.append(client)
                    local.embedding=WorkersAIEmbeddingClient(self.embedding.settings,client)
                else: local.embedding=self.embedding
            batch=local.embedding.embed(tuple(c['body_text'] for c in chunks))
            if batch.signature!=signature: raise EmbeddingWriteConflict("Embedding configuration changed during corpus indexing")
            return self.repository.save_batch(plan,access,chunks,batch)
        try:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                queued=deque();futures=set();issued=0;exhausted=False;error=None
                def fill_workers():
                    nonlocal after,issued,exhausted
                    while not exhausted and len(futures)<workers and (max_batches is None or issued<max_batches):
                        if not queued:
                            width=workers if max_batches is None else min(workers,max_batches-issued)
                            chunks=self.repository.pending(plan,access,signature,width*batch_size,after)
                            if not chunks: exhausted=True;break
                            queued.extend(chunks[start:start+batch_size] for start in range(0,len(chunks),batch_size))
                            last=chunks[-1];after=(last['document_id'],last['document_version'],last['chunk_index'])
                        futures.add(pool.submit(work,queued.popleft()));issued+=1
                fill_workers()
                while futures:
                    done,futures=wait(futures,return_when=FIRST_COMPLETED)
                    for future in done:
                        try: written+=future.result();completed+=1
                        except Exception as failure: error=error or failure
                        progress({"phase":"embedding","completed_batches":completed,"vectors_written":written,
                                  "ready_vectors_at_least":initial_ready+written,"expected_chunks":plan.chunk_count})
                    # Stop submitting on failure, but settle all outstanding guarded writes.
                    if error is None: fill_workers()
                if error: raise error
        finally:
            for client in clients: client.close()
        status=self.repository.status(plan,access,signature)
        if status['ready_vectors']!=plan.chunk_count:
            if max_batches is not None and completed>=max_batches:
                return {"status":"partial",**status,"vectors_written":written,"completed_batches":completed}
            raise EmbeddingWriteConflict("Corpus has inaccessible, superseded or unindexed chunks")
        # Publish only once the full pinned corpus has valid vectors; each document activation is atomic.
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures=[pool.submit(self.documents.index,d.document_id,d.document_version,access) for d in plan.documents]
            error=None;activated=0
            for future in as_completed(futures):
                try: future.result();activated+=1
                except Exception as failure: error=error or failure
                if activated==1 or activated%100==0 or activated==len(plan.documents):
                    progress({"phase":"activation","active_documents":activated,"expected_documents":len(plan.documents)})
            if error: raise error
        status=self.repository.status(plan,access,signature)
        if status['active_documents']!=len(plan.documents): raise EmbeddingWriteConflict("Corpus activation is incomplete")
        return {"status":"complete",**status,"vectors_written":written,"completed_batches":completed}
