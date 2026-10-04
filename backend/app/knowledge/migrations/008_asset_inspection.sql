-- Asset lifecycle is a safety boundary, independent of model output and telemetry.
ALTER TABLE dataops.asset_versions DROP CONSTRAINT asset_versions_status_check;
ALTER TABLE dataops.asset_versions ADD CONSTRAINT asset_versions_status_check
    CHECK (status IN ('uploading','quarantined','scanning','ready','rejected'));

CREATE TABLE dataops.asset_inspections (
    tenant_id text NOT NULL,
    inspection_id text NOT NULL,
    asset_version_id text NOT NULL,
    outcome text NOT NULL CHECK (outcome IN ('passed','rejected','failed')),
    size_bytes bigint,
    sha256 text CHECK (sha256 ~ '^[a-f0-9]{64}$'),
    media_type text,
    malware_clean boolean,
    reason_code text,
    checked_by text NOT NULL,
    policy_version text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (tenant_id, inspection_id),
    FOREIGN KEY (tenant_id, asset_version_id)
        REFERENCES dataops.asset_versions (tenant_id, asset_version_id),
    CHECK (outcome <> 'passed' OR
        (size_bytes IS NOT NULL AND size_bytes > 0 AND sha256 IS NOT NULL AND media_type IS NOT NULL
         AND media_type <> 'application/octet-stream' AND malware_clean IS TRUE
         AND reason_code IS NULL))
);
CREATE INDEX asset_inspection_version_idx
    ON dataops.asset_inspections (tenant_id, asset_version_id, created_at);
CREATE TRIGGER asset_inspection_immutable BEFORE UPDATE OR DELETE ON dataops.asset_inspections
    FOR EACH ROW EXECUTE FUNCTION retrieval.reject_raw_mutation();

CREATE OR REPLACE FUNCTION dataops.guard_asset_version() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'Asset versions are retained'; END IF;
    IF TG_OP = 'INSERT' THEN
        IF NEW.status <> 'uploading' OR NEW.ready_object_id IS NOT NULL OR
           NEW.sha256 IS NOT NULL OR NEW.media_type IS NOT NULL OR NEW.rejection_code IS NOT NULL THEN
            RAISE EXCEPTION 'Asset versions must start uploading without verification claims';
        END IF;
        RETURN NEW;
    END IF;
    IF OLD.status IN ('ready','rejected') OR
       (to_jsonb(OLD) - ARRAY['status','sha256','media_type','ready_object_id','rejection_code']) IS DISTINCT FROM
       (to_jsonb(NEW) - ARRAY['status','sha256','media_type','ready_object_id','rejection_code']) OR
       NOT ((OLD.status = 'uploading' AND NEW.status = 'quarantined') OR
            (OLD.status = 'quarantined' AND NEW.status = 'scanning') OR
            (OLD.status = 'scanning' AND NEW.status IN ('ready','rejected','quarantined'))) THEN
        RAISE EXCEPTION 'Invalid asset state transition or immutable identity change';
    END IF;
    IF NEW.status = 'ready' AND NOT EXISTS (
        SELECT 1 FROM dataops.asset_inspections i
        WHERE (i.tenant_id,i.asset_version_id) = (NEW.tenant_id,NEW.asset_version_id)
          AND i.outcome = 'passed' AND i.size_bytes = NEW.size_bytes
          AND i.sha256 = NEW.sha256 AND i.media_type = NEW.media_type
          AND i.malware_clean IS TRUE
    ) THEN RAISE EXCEPTION 'Ready requires matching successful inspection facts'; END IF;
    IF OLD.status = 'scanning' AND NEW.status IN ('rejected','quarantined') AND NOT EXISTS (
        SELECT 1 FROM dataops.asset_inspections i
        WHERE (i.tenant_id,i.asset_version_id) = (NEW.tenant_id,NEW.asset_version_id)
          AND ((NEW.status = 'rejected' AND i.outcome = 'rejected' AND i.reason_code = NEW.rejection_code)
            OR (NEW.status = 'quarantined' AND i.outcome = 'failed'))
    ) THEN RAISE EXCEPTION 'Inspection failure must be recorded before changing state'; END IF;
    IF NEW.status IN ('scanning','quarantined') AND
       (NEW.sha256 IS NOT NULL OR NEW.media_type IS NOT NULL OR
        NEW.ready_object_id IS NOT NULL OR NEW.rejection_code IS NOT NULL) THEN
        RAISE EXCEPTION 'Pending asset versions cannot claim verification';
    END IF;
    RETURN NEW;
END;
$$;
DROP TRIGGER asset_version_guard ON dataops.asset_versions;
CREATE TRIGGER asset_version_guard BEFORE INSERT OR UPDATE OR DELETE ON dataops.asset_versions
    FOR EACH ROW EXECUTE FUNCTION dataops.guard_asset_version();

CREATE FUNCTION dataops.require_ready_artifact_source() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE source_status text;
BEGIN
    SELECT status INTO source_status FROM dataops.asset_versions
        WHERE (tenant_id,asset_version_id) = (NEW.tenant_id,NEW.asset_version_id) FOR SHARE;
    IF source_status IS DISTINCT FROM 'ready' THEN
        RAISE EXCEPTION 'Derived artifacts require a ready asset version in the same tenant';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER derived_artifact_source_guard BEFORE INSERT ON dataops.derived_artifacts
    FOR EACH ROW EXECUTE FUNCTION dataops.require_ready_artifact_source();
