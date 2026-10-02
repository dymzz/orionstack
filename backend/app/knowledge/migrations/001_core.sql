-- One database: relational knowledge and pgvector share tenant-aware provenance.
CREATE EXTENSION IF NOT EXISTS vector;
CREATE SCHEMA IF NOT EXISTS business;
CREATE SCHEMA IF NOT EXISTS retrieval;
CREATE SCHEMA IF NOT EXISTS integration;

CREATE TABLE core.source_records (
    tenant_id text NOT NULL,
    source_record_id text NOT NULL,
    source_version text NOT NULL,
    source_system text NOT NULL,
    external_id text NOT NULL,
    source_locator text NOT NULL CHECK (source_locator <> ''),
    title text NOT NULL DEFAULT '',
    raw_content text NOT NULL DEFAULT '',
    content_hash text NOT NULL CHECK (content_hash ~ '^[0-9a-f]{64}$'),
    access_scope text NOT NULL,
    lifecycle_status text NOT NULL CHECK (lifecycle_status IN
        ('active', 'draft', 'pending', 'revoked', 'deleted', 'archived', 'superseded')),
    metadata jsonb NOT NULL DEFAULT '{}',
    PRIMARY KEY (tenant_id, source_record_id, source_version)
);
CREATE INDEX source_origin_idx ON core.source_records
    (tenant_id, source_system, external_id);

CREATE TABLE core.documents (
    tenant_id text NOT NULL,
    document_id text NOT NULL,
    document_version text NOT NULL,
    source_record_id text NOT NULL,
    source_version text NOT NULL,
    filename text NOT NULL,
    storage_locator text NOT NULL,
    content_hash text NOT NULL CHECK (content_hash ~ '^[0-9a-f]{64}$'),
    access_scope text NOT NULL,
    lifecycle_status text NOT NULL CHECK (lifecycle_status IN
        ('active', 'draft', 'pending', 'revoked', 'deleted', 'archived', 'superseded')),
    metadata jsonb NOT NULL DEFAULT '{}',
    PRIMARY KEY (tenant_id, document_id, document_version),
    FOREIGN KEY (tenant_id, source_record_id, source_version)
        REFERENCES core.source_records (tenant_id, source_record_id, source_version)
);

CREATE TABLE core.document_chunks (
    tenant_id text NOT NULL,
    chunk_id text NOT NULL,
    document_id text NOT NULL,
    document_version text NOT NULL,
    chunk_index integer NOT NULL CHECK (chunk_index >= 0),
    body_text text NOT NULL CHECK (body_text <> ''),
    content_hash text NOT NULL CHECK (content_hash ~ '^[0-9a-f]{64}$'),
    source_locator text NOT NULL,
    access_scope text NOT NULL,
    lifecycle_status text NOT NULL CHECK (lifecycle_status IN
        ('active', 'draft', 'pending', 'revoked', 'deleted', 'archived', 'superseded')),
    embedding vector,
    embedding_model text,
    embedding_dimensions integer,
    embedding_content_hash text,
    metadata jsonb NOT NULL DEFAULT '{}',
    PRIMARY KEY (tenant_id, chunk_id, document_version),
    FOREIGN KEY (tenant_id, document_id, document_version)
        REFERENCES core.documents (tenant_id, document_id, document_version),
    CHECK ((embedding IS NULL AND embedding_model IS NULL
            AND embedding_dimensions IS NULL AND embedding_content_hash IS NULL)
        OR (embedding IS NOT NULL AND embedding_model IS NOT NULL
            AND embedding_dimensions IS NOT NULL AND embedding_content_hash IS NOT NULL
            AND embedding_model <> '' AND embedding_dimensions > 0
            AND vector_dims(embedding) = embedding_dimensions
            AND embedding_content_hash = content_hash))
);
CREATE INDEX chunk_filter_idx ON core.document_chunks
    (tenant_id, lifecycle_status, access_scope, document_id);
-- A model/dimension-specific vector index is added after the embedding model is chosen.

CREATE TABLE core.knowledge_units (
    tenant_id text NOT NULL,
    unit_id text NOT NULL,
    unit_version text NOT NULL,
    source_record_id text NOT NULL,
    source_version text NOT NULL,
    question text NOT NULL,
    answer text NOT NULL,
    content_hash text NOT NULL CHECK (content_hash ~ '^[0-9a-f]{64}$'),
    access_scope text NOT NULL,
    lifecycle_status text NOT NULL CHECK (lifecycle_status IN
        ('active', 'draft', 'pending', 'revoked', 'deleted', 'archived', 'superseded')),
    metadata jsonb NOT NULL DEFAULT '{}',
    PRIMARY KEY (tenant_id, unit_id, unit_version),
    FOREIGN KEY (tenant_id, source_record_id, source_version)
        REFERENCES core.source_records (tenant_id, source_record_id, source_version)
);

-- Entity directory; typed business domain tables are introduced with structured queries.
CREATE TABLE business.entities (
    tenant_id text NOT NULL,
    entity_type text NOT NULL,
    entity_id text NOT NULL,
    source_record_id text NOT NULL,
    source_version text NOT NULL,
    access_scope text NOT NULL,
    lifecycle_status text NOT NULL CHECK (lifecycle_status IN
        ('active', 'draft', 'pending', 'revoked', 'deleted', 'archived', 'superseded')),
    attributes jsonb NOT NULL DEFAULT '{}',
    PRIMARY KEY (tenant_id, entity_type, entity_id),
    FOREIGN KEY (tenant_id, source_record_id, source_version)
        REFERENCES core.source_records (tenant_id, source_record_id, source_version)
);
CREATE TABLE business.entity_documents (
    tenant_id text NOT NULL,
    entity_type text NOT NULL,
    entity_id text NOT NULL,
    document_id text NOT NULL,
    document_version text NOT NULL,
    PRIMARY KEY (tenant_id, entity_type, entity_id, document_id, document_version),
    FOREIGN KEY (tenant_id, entity_type, entity_id)
        REFERENCES business.entities (tenant_id, entity_type, entity_id),
    FOREIGN KEY (tenant_id, document_id, document_version)
        REFERENCES core.documents (tenant_id, document_id, document_version)
);

CREATE TABLE core.import_batches (
    batch_id text PRIMARY KEY,
    snapshot_hash text NOT NULL UNIQUE,
    counts jsonb NOT NULL,
    imported_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE retrieval.query_runs (
    tenant_id text NOT NULL,
    request_id text NOT NULL,
    user_id text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    decisions jsonb NOT NULL DEFAULT '{}',
    PRIMARY KEY (tenant_id, request_id)
);
CREATE TABLE retrieval.evidence_snapshots (
    tenant_id text NOT NULL,
    request_id text NOT NULL,
    evidence_id text NOT NULL,
    snapshot jsonb NOT NULL,
    PRIMARY KEY (tenant_id, request_id, evidence_id),
    FOREIGN KEY (tenant_id, request_id)
        REFERENCES retrieval.query_runs (tenant_id, request_id)
);

CREATE TABLE integration.actions (
    tenant_id text NOT NULL,
    action_id text NOT NULL,
    action text NOT NULL,
    request_id text NOT NULL,
    user_id text NOT NULL,
    payload_hash text NOT NULL,
    payload jsonb NOT NULL,
    status text NOT NULL CHECK (status IN ('accepted', 'succeeded', 'failed', 'unknown')),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (tenant_id, action_id),
    UNIQUE (tenant_id, action, request_id)
);
CREATE TABLE integration.events (
    tenant_id text NOT NULL,
    event_id text NOT NULL,
    payload_hash text NOT NULL,
    payload jsonb NOT NULL,
    received_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (tenant_id, event_id)
);
