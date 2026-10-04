-- DataOps Asset metadata. Binary objects stay outside PostgreSQL.
CREATE SCHEMA IF NOT EXISTS dataops;
CREATE TABLE dataops.assets (
    tenant_id text NOT NULL CHECK (tenant_id <> ''),
    asset_id text NOT NULL,
    kind text NOT NULL,
    created_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (tenant_id, asset_id)
);
CREATE TABLE dataops.storage_objects (
    tenant_id text NOT NULL,
    object_id text NOT NULL,
    object_key text NOT NULL,
    provider_version_id text,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (tenant_id, object_id),
    UNIQUE (tenant_id, object_key)
);
CREATE TABLE dataops.asset_versions (
    tenant_id text NOT NULL,
    asset_version_id text NOT NULL,
    asset_id text NOT NULL,
    version integer NOT NULL CHECK (version > 0),
    upload_object_id text NOT NULL,
    ready_object_id text,
    expected_sha256 text CHECK (expected_sha256 ~ '^[a-f0-9]{64}$'),
    sha256 text CHECK (sha256 ~ '^[a-f0-9]{64}$'),
    size_bytes bigint NOT NULL CHECK (size_bytes > 0 AND size_bytes <= 134217728),
    media_type_hint text NOT NULL,
    media_type text,
    original_filename text NOT NULL,
    relative_path text NOT NULL DEFAULT '',
    created_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status text NOT NULL CHECK (status IN ('uploading','quarantined','ready','rejected')),
    rejection_code text,
    PRIMARY KEY (tenant_id, asset_version_id),
    UNIQUE (tenant_id, asset_id, version),
    FOREIGN KEY (tenant_id, asset_id) REFERENCES dataops.assets (tenant_id, asset_id),
    FOREIGN KEY (tenant_id, upload_object_id) REFERENCES dataops.storage_objects (tenant_id, object_id),
    FOREIGN KEY (tenant_id, ready_object_id) REFERENCES dataops.storage_objects (tenant_id, object_id),
    CHECK (status <> 'ready' OR (sha256 IS NOT NULL AND media_type IS NOT NULL AND ready_object_id IS NOT NULL))
);
CREATE TABLE dataops.attachment_links (
    tenant_id text NOT NULL,
    resource_type text NOT NULL CHECK (resource_type IN ('document','collection')),
    resource_id text NOT NULL,
    asset_id text NOT NULL,
    relation text NOT NULL CHECK (relation IN ('drawing','invoice','site_photo','supporting_document','contract','other')),
    PRIMARY KEY (tenant_id, asset_id),
    FOREIGN KEY (tenant_id, asset_id) REFERENCES dataops.assets (tenant_id, asset_id)
);
CREATE TABLE dataops.derived_artifacts (
    tenant_id text NOT NULL,
    artifact_id text NOT NULL,
    asset_version_id text NOT NULL,
    kind text NOT NULL CHECK (kind IN ('ocr_text','thumbnail','extracted_metadata','embedding_chunks')),
    producer text NOT NULL,
    producer_version text NOT NULL,
    content_hash text NOT NULL CHECK (content_hash ~ '^[a-f0-9]{64}$'),
    object_id text,
    evidence_id text,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (tenant_id, artifact_id),
    FOREIGN KEY (tenant_id, asset_version_id) REFERENCES dataops.asset_versions (tenant_id, asset_version_id),
    FOREIGN KEY (tenant_id, object_id) REFERENCES dataops.storage_objects (tenant_id, object_id)
);
CREATE TABLE dataops.audit_events (
    tenant_id text NOT NULL,
    id text NOT NULL,
    principal_id text NOT NULL,
    action text NOT NULL,
    resource_type text NOT NULL,
    resource_id text NOT NULL,
    decision text NOT NULL,
    policy_version text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (tenant_id, id)
);
CREATE INDEX asset_owner_idx ON dataops.assets (tenant_id, created_by);
CREATE TRIGGER storage_object_immutable BEFORE UPDATE OR DELETE ON dataops.storage_objects
    FOR EACH ROW EXECUTE FUNCTION retrieval.reject_raw_mutation();
CREATE TRIGGER asset_identity_immutable BEFORE UPDATE OR DELETE ON dataops.assets
    FOR EACH ROW EXECUTE FUNCTION retrieval.reject_raw_mutation();
CREATE TRIGGER attachment_link_immutable BEFORE UPDATE OR DELETE ON dataops.attachment_links
    FOR EACH ROW EXECUTE FUNCTION retrieval.reject_raw_mutation();
CREATE TRIGGER derived_artifact_immutable BEFORE UPDATE OR DELETE ON dataops.derived_artifacts
    FOR EACH ROW EXECUTE FUNCTION retrieval.reject_raw_mutation();
CREATE TRIGGER dataops_audit_immutable BEFORE UPDATE OR DELETE ON dataops.audit_events
    FOR EACH ROW EXECUTE FUNCTION retrieval.reject_raw_mutation();
CREATE FUNCTION dataops.guard_asset_version() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'Asset versions are retained'; END IF;
    IF OLD.status IN ('ready','rejected') OR
       (to_jsonb(OLD) - ARRAY['status','sha256','media_type','ready_object_id','rejection_code']) IS DISTINCT FROM
       (to_jsonb(NEW) - ARRAY['status','sha256','media_type','ready_object_id','rejection_code']) OR
       NOT ((OLD.status = 'uploading' AND NEW.status = 'quarantined') OR
            (OLD.status = 'quarantined' AND NEW.status IN ('ready','rejected'))) THEN
        RAISE EXCEPTION 'Asset identity is immutable and quarantine is required';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER asset_version_guard BEFORE UPDATE OR DELETE ON dataops.asset_versions
    FOR EACH ROW EXECUTE FUNCTION dataops.guard_asset_version();
