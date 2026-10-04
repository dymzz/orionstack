-- P0: explicit legacy quarantine, original upload bytes, and answer audit.
CREATE TABLE core.quarantined_legacy_records (
    tenant_id text NOT NULL,
    payload_hash text NOT NULL CHECK (payload_hash ~ '^[0-9a-f]{64}$'),
    unit_id text NOT NULL,
    source_record_id text NOT NULL,
    origin text NOT NULL,
    payload jsonb NOT NULL,
    resolution jsonb NOT NULL,
    quarantined_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (tenant_id, payload_hash)
);

CREATE TABLE core.document_files (
    tenant_id text NOT NULL,
    document_id text NOT NULL,
    document_version text NOT NULL,
    data bytea NOT NULL,
    content_type text NOT NULL,
    PRIMARY KEY (tenant_id, document_id, document_version),
    FOREIGN KEY (tenant_id, document_id, document_version)
        REFERENCES core.documents (tenant_id, document_id, document_version)
);

CREATE TABLE core.document_heads (
    tenant_id text NOT NULL,
    document_id text NOT NULL,
    target_version text NOT NULL,
    PRIMARY KEY (tenant_id, document_id),
    FOREIGN KEY (tenant_id, document_id, target_version)
        REFERENCES core.documents (tenant_id, document_id, document_version)
);

CREATE TABLE retrieval.answer_runs (
    tenant_id text NOT NULL,
    event_id text NOT NULL,
    id text NOT NULL,
    user_id text NOT NULL,
    status text NOT NULL CHECK (status IN ('answered', 'insufficient_evidence', 'failed')),
    response jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (tenant_id, id),
    FOREIGN KEY (tenant_id, event_id) REFERENCES retrieval.retrieval_event (tenant_id, id)
);

-- Content/provenance is versioned. Scope/lifecycle and embeddings may change;
-- replacing original content requires a new version instead of rewriting one.
CREATE FUNCTION core.reject_content_rewrite() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE old_content jsonb; new_content jsonb;
BEGIN
    old_content := to_jsonb(OLD) - ARRAY['access_scope','lifecycle_status','metadata',
        'embedding','embedding_model','embedding_dimensions','embedding_content_hash','embedding_signature'];
    new_content := to_jsonb(NEW) - ARRAY['access_scope','lifecycle_status','metadata',
        'embedding','embedding_model','embedding_dimensions','embedding_content_hash','embedding_signature'];
    IF old_content IS DISTINCT FROM new_content THEN
        RAISE EXCEPTION 'Content and provenance require a new version';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER source_content_versioned BEFORE UPDATE ON core.source_records
    FOR EACH ROW EXECUTE FUNCTION core.reject_content_rewrite();
CREATE TRIGGER document_content_versioned BEFORE UPDATE ON core.documents
    FOR EACH ROW EXECUTE FUNCTION core.reject_content_rewrite();
CREATE TRIGGER chunk_content_versioned BEFORE UPDATE ON core.document_chunks
    FOR EACH ROW EXECUTE FUNCTION core.reject_content_rewrite();
CREATE TRIGGER document_file_immutable BEFORE UPDATE OR DELETE ON core.document_files
    FOR EACH ROW EXECUTE FUNCTION retrieval.reject_raw_mutation();
