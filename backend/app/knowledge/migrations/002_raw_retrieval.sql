-- Additive migration: never rewrite the checksum of 001_core.
ALTER TABLE core.document_chunks ADD COLUMN embedding_signature text
    CHECK (embedding_signature IS NULL OR embedding_signature ~ '^[0-9a-f]{64}$');
CREATE INDEX chunk_embedding_signature_idx ON core.document_chunks
    (tenant_id, embedding_signature, lifecycle_status, document_id);

CREATE TABLE retrieval.retrieval_event (
    tenant_id text NOT NULL,
    id text NOT NULL,
    user_id text NOT NULL,
    query text NOT NULL CHECK (query <> ''),
    query_hash text NOT NULL CHECK (query_hash ~ '^[0-9a-f]{64}$'),
    embedding_signature text NOT NULL CHECK (embedding_signature ~ '^[0-9a-f]{64}$'),
    embedding_configuration jsonb NOT NULL,
    query_vector jsonb NOT NULL CHECK (jsonb_typeof(query_vector) = 'array'),
    document_ids jsonb NOT NULL,
    allowed_scopes jsonb NOT NULL,
    top_k integer NOT NULL CHECK (top_k BETWEEN 1 AND 100),
    candidate_count integer NOT NULL CHECK (candidate_count >= 0 AND candidate_count <= top_k),
    retrieval_method text NOT NULL CHECK (retrieval_method = 'pgvector_exact_cosine'),
    created_at timestamptz NOT NULL,
    PRIMARY KEY (tenant_id, id)
);
CREATE INDEX retrieval_event_created_idx ON retrieval.retrieval_event (tenant_id, created_at);

CREATE TABLE retrieval.retrieval_candidate (
    tenant_id text NOT NULL,
    event_id text NOT NULL,
    id text NOT NULL,
    document_id text NOT NULL,
    document_version text NOT NULL,
    chunk_id text NOT NULL,
    content_hash text NOT NULL CHECK (content_hash ~ '^[0-9a-f]{64}$'),
    rank integer NOT NULL CHECK (rank > 0),
    similarity_score double precision NOT NULL
        CHECK (similarity_score > '-Infinity'::float8 AND similarity_score < 'Infinity'::float8),
    raw_snapshot jsonb NOT NULL,
    snapshot_hash text NOT NULL CHECK (snapshot_hash ~ '^[0-9a-f]{64}$'),
    PRIMARY KEY (tenant_id, event_id, id),
    UNIQUE (tenant_id, event_id, rank),
    UNIQUE (tenant_id, event_id, document_id, document_version, chunk_id),
    FOREIGN KEY (tenant_id, event_id) REFERENCES retrieval.retrieval_event (tenant_id, id)
        DEFERRABLE INITIALLY DEFERRED
);

CREATE FUNCTION retrieval.reject_raw_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'Raw retrieval records are immutable';
END;
$$;
CREATE TRIGGER retrieval_event_immutable BEFORE UPDATE OR DELETE ON retrieval.retrieval_event
    FOR EACH ROW EXECUTE FUNCTION retrieval.reject_raw_mutation();
CREATE TRIGGER retrieval_candidate_immutable BEFORE UPDATE OR DELETE ON retrieval.retrieval_candidate
    FOR EACH ROW EXECUTE FUNCTION retrieval.reject_raw_mutation();
CREATE TRIGGER retrieval_event_no_truncate BEFORE TRUNCATE ON retrieval.retrieval_event
    FOR EACH STATEMENT EXECUTE FUNCTION retrieval.reject_raw_mutation();
CREATE TRIGGER retrieval_candidate_no_truncate BEFORE TRUNCATE ON retrieval.retrieval_candidate
    FOR EACH STATEMENT EXECUTE FUNCTION retrieval.reject_raw_mutation();

-- Insert candidates first, then seal the event in the same transaction.
CREATE FUNCTION retrieval.reject_late_candidate() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF EXISTS (SELECT 1 FROM retrieval.retrieval_event
               WHERE tenant_id = NEW.tenant_id AND id = NEW.event_id) THEN
        RAISE EXCEPTION 'Cannot append candidates to a sealed retrieval event';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER retrieval_candidate_sealed BEFORE INSERT ON retrieval.retrieval_candidate
    FOR EACH ROW EXECUTE FUNCTION retrieval.reject_late_candidate();

-- Deferred validation also rejects incomplete or concurrent late insertions.
CREATE FUNCTION retrieval.verify_raw_set() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    event_key text;
    expected integer;
    actual integer;
    first_rank integer;
    last_rank integer;
BEGIN
    IF TG_TABLE_NAME = 'retrieval_event' THEN event_key := NEW.id;
    ELSE event_key := NEW.event_id; END IF;
    SELECT candidate_count INTO expected FROM retrieval.retrieval_event
        WHERE tenant_id = NEW.tenant_id AND id = event_key;
    SELECT count(*), min(rank), max(rank) INTO actual, first_rank, last_rank
        FROM retrieval.retrieval_candidate WHERE tenant_id = NEW.tenant_id AND event_id = event_key;
    IF expected IS NULL OR actual <> expected
       OR (actual > 0 AND (first_rank <> 1 OR last_rank <> actual)) THEN
        RAISE EXCEPTION 'Raw retrieval event has an incomplete candidate set';
    END IF;
    RETURN NULL;
END;
$$;
CREATE CONSTRAINT TRIGGER retrieval_event_complete AFTER INSERT ON retrieval.retrieval_event
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION retrieval.verify_raw_set();
CREATE CONSTRAINT TRIGGER retrieval_candidate_complete AFTER INSERT ON retrieval.retrieval_candidate
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION retrieval.verify_raw_set();

CREATE TABLE retrieval.processing_run (
    tenant_id text NOT NULL,
    event_id text NOT NULL,
    id text NOT NULL,
    policy jsonb NOT NULL,
    status text NOT NULL CHECK (status IN ('completed', 'raw_fallback')),
    error_code text,
    created_at timestamptz NOT NULL,
    PRIMARY KEY (tenant_id, event_id, id),
    FOREIGN KEY (tenant_id, event_id) REFERENCES retrieval.retrieval_event (tenant_id, id)
);
CREATE TABLE retrieval.retrieval_evaluation (
    tenant_id text NOT NULL,
    event_id text NOT NULL,
    id text NOT NULL,
    candidate_id text,
    processing_run_id text,
    evaluator text NOT NULL,
    evaluator_version text NOT NULL,
    decision text NOT NULL,
    score double precision CHECK (score > '-Infinity'::float8 AND score < 'Infinity'::float8),
    reason text NOT NULL DEFAULT '',
    details jsonb NOT NULL DEFAULT '{}',
    created_at timestamptz NOT NULL,
    PRIMARY KEY (tenant_id, event_id, id),
    FOREIGN KEY (tenant_id, event_id) REFERENCES retrieval.retrieval_event (tenant_id, id),
    FOREIGN KEY (tenant_id, event_id, candidate_id)
        REFERENCES retrieval.retrieval_candidate (tenant_id, event_id, id),
    FOREIGN KEY (tenant_id, event_id, processing_run_id)
        REFERENCES retrieval.processing_run (tenant_id, event_id, id)
);
CREATE TABLE retrieval.processing_result (
    tenant_id text NOT NULL,
    event_id text NOT NULL,
    processing_run_id text NOT NULL,
    candidate_id text NOT NULL,
    rank integer NOT NULL CHECK (rank > 0),
    PRIMARY KEY (tenant_id, event_id, processing_run_id, candidate_id),
    UNIQUE (tenant_id, event_id, processing_run_id, rank),
    FOREIGN KEY (tenant_id, event_id, processing_run_id)
        REFERENCES retrieval.processing_run (tenant_id, event_id, id),
    FOREIGN KEY (tenant_id, event_id, candidate_id)
        REFERENCES retrieval.retrieval_candidate (tenant_id, event_id, id)
);

CREATE TABLE retrieval.training_example (
    tenant_id text NOT NULL,
    id text NOT NULL,
    dataset_version text NOT NULL,
    event_id text NOT NULL,
    query text NOT NULL,
    positives jsonb NOT NULL,
    hard_negatives jsonb NOT NULL,
    label_provenance jsonb NOT NULL,
    created_at timestamptz NOT NULL,
    PRIMARY KEY (tenant_id, id),
    UNIQUE (tenant_id, dataset_version, event_id),
    FOREIGN KEY (tenant_id, event_id) REFERENCES retrieval.retrieval_event (tenant_id, id)
);
