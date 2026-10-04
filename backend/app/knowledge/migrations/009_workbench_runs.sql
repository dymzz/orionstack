-- QA run receipts and ordinary conversation are independent of retrieval raw.
CREATE SCHEMA IF NOT EXISTS qa;
CREATE TABLE qa.workbench_runs (
    tenant_id text NOT NULL,
    id text NOT NULL,
    user_id text NOT NULL,
    access_snapshot jsonb NOT NULL,
    mode text NOT NULL CHECK (mode IN ('knowledge', 'general_chat')),
    request_payload jsonb NOT NULL,
    request_hash text NOT NULL CHECK (request_hash ~ '^[0-9a-f]{64}$'),
    status text NOT NULL CHECK (status IN ('answered', 'insufficient_evidence', 'failed')),
    retrieval_event_id text,
    response jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (tenant_id, id),
    FOREIGN KEY (tenant_id, retrieval_event_id) REFERENCES retrieval.retrieval_event (tenant_id, id),
    CHECK (mode <> 'general_chat' OR retrieval_event_id IS NULL)
);
CREATE INDEX workbench_runs_actor ON qa.workbench_runs (tenant_id, user_id, created_at);
CREATE TRIGGER workbench_runs_immutable BEFORE UPDATE OR DELETE ON qa.workbench_runs
    FOR EACH ROW EXECUTE FUNCTION retrieval.reject_raw_mutation();
CREATE TRIGGER workbench_runs_no_truncate BEFORE TRUNCATE ON qa.workbench_runs
    FOR EACH STATEMENT EXECUTE FUNCTION retrieval.reject_raw_mutation();
