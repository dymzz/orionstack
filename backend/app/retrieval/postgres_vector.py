"""Exact pgvector recall with mandatory permissions, followed by raw journal sealing."""

from app.knowledge.contracts import AccessContext, QueryContext, SourceRef, content_hash
from app.knowledge.embedding import EmbeddingBatch, EmbeddingSignature, normalized_vector
from app.knowledge.postgres import PostgresDatabase
from app.retrieval.raw_contracts import RawCandidate, RawRetrievalEvent, RawRetrievalRecord
from app.retrieval.raw_journal import PostgresRawJournal
from app.config.runtime_versions import runtime_versions


VECTOR_SEARCH_SQL = """
    SELECT c.document_id, c.document_version, c.chunk_id, c.body_text, c.content_hash,
           c.source_locator, c.access_scope AS chunk_scope, d.access_scope AS document_scope,
           s.access_scope AS source_scope, d.source_record_id, d.source_version,
           1 - (c.embedding <=> %s::vector) AS similarity_score
    FROM core.document_chunks c
    JOIN core.documents d ON (c.tenant_id, c.document_id, c.document_version) =
                             (d.tenant_id, d.document_id, d.document_version)
    JOIN core.source_records s ON (d.tenant_id, d.source_record_id, d.source_version) =
                                  (s.tenant_id, s.source_record_id, s.source_version)
    WHERE c.tenant_id = %s
      AND c.lifecycle_status = 'active' AND d.lifecycle_status = 'active' AND s.lifecycle_status = 'active'
      AND c.access_scope = ANY(%s::text[]) AND d.access_scope = ANY(%s::text[]) AND s.access_scope = ANY(%s::text[])
      AND c.embedding IS NOT NULL AND c.embedding_signature = %s
      AND c.embedding_model = %s AND c.embedding_dimensions = %s
      AND c.embedding_content_hash = c.content_hash
      AND (cardinality(%s::text[]) = 0 OR c.document_id = ANY(%s::text[]))
    ORDER BY c.embedding <=> %s::vector, c.document_id, c.document_version, c.chunk_id
    LIMIT %s
"""


def vector_literal(vector: tuple[float, ...]) -> str:
    return "[" + ",".join(repr(value) for value in vector) + "]"


class PostgresVectorRetriever:
    def __init__(self, database: PostgresDatabase | None = None, journal: PostgresRawJournal | None = None) -> None:
        self.database = database or PostgresDatabase()
        self.journal = journal or PostgresRawJournal(self.database)

    def retrieve_and_record(self, context: QueryContext, access: AccessContext,
                            embedding: EmbeddingBatch, top_k: int = 20) -> RawRetrievalRecord:
        from psycopg.rows import dict_row
        if isinstance(top_k, bool) or not 1 <= top_k <= 100:
            raise ValueError("Raw top_k must be between 1 and 100")
        if context.entities:
            raise ValueError("Entity context must be resolved to authorized document scope before vector retrieval")
        if len(embedding.vectors) != 1 or embedding.input_hashes != (content_hash(context.query),):
            raise ValueError("Query embedding does not match the actual query")
        vector = embedding.vectors[0]
        normalized_vector(vector, embedding.signature.dimensions)  # shape and finite/nonzero validation
        literal = vector_literal(vector)
        scopes = list(access.allowed_scopes)
        documents = list(context.document_ids)
        with self.database.connection() as connection:
            with connection.transaction():
                with connection.cursor(row_factory=dict_row) as cursor:
                    rows = cursor.execute(VECTOR_SEARCH_SQL, (
                        literal, access.tenant_id, scopes, scopes, scopes, embedding.signature.fingerprint,
                        embedding.signature.model, embedding.signature.dimensions, documents, documents, literal, top_k,
                    )).fetchall()
                candidates = tuple(RawCandidate(
                    document_id=row["document_id"], document_version=row["document_version"],
                    chunk_id=row["chunk_id"], content_hash=row["content_hash"], rank=rank,
                    similarity_score=row["similarity_score"], text=row["body_text"],
                    source=SourceRef(source_id=row["source_record_id"], source_version=row["source_version"],
                                     source_locator=row["source_locator"], document_id=row["document_id"],
                                     document_version=row["document_version"], chunk_id=row["chunk_id"],
                                     content_hash=row["content_hash"]),
                    access_scopes=tuple(dict.fromkeys((row["chunk_scope"], row["document_scope"], row["source_scope"]))),
                ) for rank, row in enumerate(rows, 1))
                event = RawRetrievalEvent(
                    runtime_versions=runtime_versions(embedding.signature,top_k),
                    tenant_id=access.tenant_id, user_id=access.user_id, query=context.query,
                    query_hash=content_hash(context.query), embedding_configuration=embedding.signature,
                    query_vector=vector, document_ids=context.document_ids, allowed_scopes=access.allowed_scopes,
                    top_k=top_k, candidate_count=len(candidates),
                )
                record = RawRetrievalRecord(event=event, candidates=candidates)
                self.journal.record_raw(connection, record, access)
            # Raw facts commit before any optional model processor is invoked.
        return record


class EmbeddingWriteConflict(RuntimeError):
    pass


class PostgresEmbeddingRepository:
    def __init__(self, database: PostgresDatabase | None = None) -> None:
        self.database = database or PostgresDatabase()

    def pending_chunks(self, access: AccessContext, signature: EmbeddingSignature, limit: int = 32) -> tuple[dict, ...]:
        from psycopg.rows import dict_row
        if not 1 <= limit <= 32:
            raise ValueError("Embedding batch size must be between 1 and 32")
        with self.database.connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                return tuple(cursor.execute("""
                    SELECT c.document_id, c.document_version, c.chunk_id, c.body_text, c.content_hash
                    FROM core.document_chunks c
                    JOIN core.documents d USING (tenant_id, document_id, document_version)
                    JOIN core.source_records s ON (d.tenant_id, d.source_record_id, d.source_version) =
                                                  (s.tenant_id, s.source_record_id, s.source_version)
                    WHERE c.tenant_id = %s
                      AND c.lifecycle_status = 'active' AND d.lifecycle_status = 'active' AND s.lifecycle_status = 'active'
                      AND c.access_scope = ANY(%s::text[]) AND d.access_scope = ANY(%s::text[]) AND s.access_scope = ANY(%s::text[])
                      AND (c.embedding IS NULL OR c.embedding_signature IS DISTINCT FROM %s)
                    ORDER BY c.document_id, c.document_version, c.chunk_index, c.chunk_id LIMIT %s
                """, (access.tenant_id, list(access.allowed_scopes), list(access.allowed_scopes),
                      list(access.allowed_scopes), signature.fingerprint, limit)).fetchall())

    def save_batch(self, access: AccessContext, chunks: tuple[dict, ...], batch: EmbeddingBatch) -> int:
        if len(chunks) != len(batch.vectors) or len(chunks) != len(batch.input_hashes):
            raise ValueError("Embedding batch does not match selected chunks")
        with self.database.connection() as connection:
            with connection.transaction():
                for chunk, vector, digest in zip(chunks, batch.vectors, batch.input_hashes):
                    normalized_vector(vector, batch.signature.dimensions)
                    if digest != chunk["content_hash"] or digest != content_hash(chunk["body_text"]):
                        raise EmbeddingWriteConflict("Chunk content changed before embedding write")
                    result = connection.execute("""
                        UPDATE core.document_chunks c
                        SET embedding = %s::vector, embedding_model = %s, embedding_dimensions = %s,
                            embedding_content_hash = %s, embedding_signature = %s
                        FROM core.documents d, core.source_records s
                        WHERE (c.tenant_id, c.document_id, c.document_version) =
                              (d.tenant_id, d.document_id, d.document_version)
                          AND (d.tenant_id, d.source_record_id, d.source_version) =
                              (s.tenant_id, s.source_record_id, s.source_version)
                          AND c.tenant_id = %s AND c.document_id = %s AND c.document_version = %s AND c.chunk_id = %s
                          AND c.content_hash = %s AND c.body_text = %s
                          AND c.lifecycle_status = 'active' AND d.lifecycle_status = 'active' AND s.lifecycle_status = 'active'
                          AND c.access_scope = ANY(%s::text[]) AND d.access_scope = ANY(%s::text[]) AND s.access_scope = ANY(%s::text[])
                    """, (vector_literal(vector), batch.signature.model, batch.signature.dimensions,
                          digest, batch.signature.fingerprint, access.tenant_id, chunk["document_id"],
                          chunk["document_version"], chunk["chunk_id"], digest, chunk["body_text"],
                          list(access.allowed_scopes), list(access.allowed_scopes), list(access.allowed_scopes)))
                    if result.rowcount != 1:
                        raise EmbeddingWriteConflict("Chunk version, lifecycle or permissions changed; batch rolled back")
        return len(chunks)
