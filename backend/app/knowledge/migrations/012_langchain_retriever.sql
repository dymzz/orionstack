-- Read adapter over the existing business schema: no copying or re-embedding.
CREATE VIEW core.retrieval_chunks AS
SELECT concat(length(c.tenant_id),':',c.tenant_id,length(c.document_version),':',
              c.document_version,length(c.chunk_id),':',c.chunk_id) AS retrieval_id,
       c.tenant_id,c.document_id,c.document_version,c.chunk_id,c.body_text,c.content_hash,
       c.source_locator,c.embedding,c.embedding::text AS vector_values,
       c.embedding_signature,c.embedding_model,c.embedding_dimensions,
       c.access_scope AS chunk_scope,d.access_scope AS document_scope,s.access_scope AS source_scope,
       d.source_record_id,d.source_version,s.title,d.filename,
       d.metadata->>'business_domain' AS business_domain,
       d.metadata->>'document_type' AS document_type,
       to_tsvector('pg_catalog.simple',c.body_text) AS body_tsv
FROM core.document_chunks c
JOIN core.documents d USING (tenant_id,document_id,document_version)
JOIN core.source_records s ON (s.tenant_id,s.source_record_id,s.source_version)=
                             (d.tenant_id,d.source_record_id,d.source_version)
WHERE c.lifecycle_status='active' AND d.lifecycle_status='active' AND s.lifecycle_status='active'
  AND c.embedding IS NOT NULL AND c.embedding_content_hash=c.content_hash;

-- Historical cosine records retain their exact method and snapshot hashes.
ALTER TABLE retrieval.retrieval_event DROP CONSTRAINT retrieval_event_retrieval_method_check;
ALTER TABLE retrieval.retrieval_event ADD CONSTRAINT retrieval_event_retrieval_method_check
    CHECK (retrieval_method IN ('pgvector_exact_cosine','pgvector_hybrid_rrf'));
