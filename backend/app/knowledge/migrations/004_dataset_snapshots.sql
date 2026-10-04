-- Reproducible corpus manifests and links to versioned documents.
CREATE TABLE core.dataset_snapshots (
    tenant_id text NOT NULL,
    dataset_id text NOT NULL,
    snapshot_hash text NOT NULL CHECK (snapshot_hash ~ '^[0-9a-f]{64}$'),
    manifest jsonb NOT NULL,
    document_count integer NOT NULL CHECK (document_count > 0),
    chunk_count integer NOT NULL CHECK (chunk_count > 0),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (tenant_id,dataset_id,snapshot_hash)
);
CREATE TABLE core.dataset_snapshot_documents (
    tenant_id text NOT NULL,
    dataset_id text NOT NULL,
    snapshot_hash text NOT NULL,
    external_id text NOT NULL,
    relative_path text NOT NULL,
    document_id text NOT NULL,
    document_version text NOT NULL,
    content_hash text NOT NULL CHECK (content_hash ~ '^[0-9a-f]{64}$'),
    chunk_count integer NOT NULL CHECK (chunk_count > 0),
    PRIMARY KEY (tenant_id,dataset_id,snapshot_hash,external_id),
    UNIQUE (tenant_id,dataset_id,snapshot_hash,relative_path),
    UNIQUE (tenant_id,dataset_id,snapshot_hash,document_id,document_version),
    FOREIGN KEY (tenant_id,dataset_id,snapshot_hash)
        REFERENCES core.dataset_snapshots (tenant_id,dataset_id,snapshot_hash),
    FOREIGN KEY (tenant_id,document_id,document_version)
        REFERENCES core.documents (tenant_id,document_id,document_version)
);
CREATE INDEX chunk_document_order_idx ON core.document_chunks
    (tenant_id,document_id,document_version,chunk_index);
CREATE TRIGGER dataset_snapshot_immutable BEFORE UPDATE OR DELETE ON core.dataset_snapshots
    FOR EACH ROW EXECUTE FUNCTION retrieval.reject_raw_mutation();
CREATE TRIGGER dataset_snapshot_no_truncate BEFORE TRUNCATE ON core.dataset_snapshots
    FOR EACH STATEMENT EXECUTE FUNCTION retrieval.reject_raw_mutation();
CREATE TRIGGER dataset_member_immutable BEFORE UPDATE OR DELETE ON core.dataset_snapshot_documents
    FOR EACH ROW EXECUTE FUNCTION retrieval.reject_raw_mutation();
CREATE TRIGGER dataset_member_no_truncate BEFORE TRUNCATE ON core.dataset_snapshot_documents
    FOR EACH STATEMENT EXECUTE FUNCTION retrieval.reject_raw_mutation();
