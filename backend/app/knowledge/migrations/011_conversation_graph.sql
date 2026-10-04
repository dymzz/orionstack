-- Business transcript is independent of LangGraph execution checkpoints.
CREATE SCHEMA IF NOT EXISTS conversation_checkpoint;
CREATE TABLE qa.conversation_threads (
    tenant_id text NOT NULL,
    id uuid NOT NULL UNIQUE,
    owner_id text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (tenant_id,id),
    UNIQUE (tenant_id,id,owner_id)
);
CREATE TABLE qa.conversation_inputs (
    tenant_id text NOT NULL,
    thread_id uuid NOT NULL,
    id uuid NOT NULL,
    owner_id text NOT NULL,
    message text NOT NULL CHECK (length(message) BETWEEN 1 AND 4000),
    payload_hash text NOT NULL CHECK (payload_hash ~ '^[0-9a-f]{64}$'),
    policy_version text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (tenant_id,thread_id,id),
    FOREIGN KEY (tenant_id,thread_id,owner_id) REFERENCES qa.conversation_threads(tenant_id,id,owner_id)
);
CREATE TABLE qa.conversation_outputs (
    tenant_id text NOT NULL,
    thread_id uuid NOT NULL,
    input_id uuid NOT NULL,
    run_id text,
    response jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (tenant_id,thread_id,input_id),
    FOREIGN KEY (tenant_id,thread_id,input_id) REFERENCES qa.conversation_inputs(tenant_id,thread_id,id),
    FOREIGN KEY (tenant_id,run_id) REFERENCES qa.workbench_runs(tenant_id,id)
);
CREATE INDEX conversation_owner ON qa.conversation_threads(tenant_id,owner_id,created_at);
CREATE INDEX conversation_transcript ON qa.conversation_inputs(tenant_id,thread_id,created_at,id);
CREATE TRIGGER conversation_threads_immutable BEFORE UPDATE OR DELETE ON qa.conversation_threads
    FOR EACH ROW EXECUTE FUNCTION retrieval.reject_raw_mutation();
CREATE TRIGGER conversation_inputs_immutable BEFORE UPDATE OR DELETE ON qa.conversation_inputs
    FOR EACH ROW EXECUTE FUNCTION retrieval.reject_raw_mutation();
CREATE TRIGGER conversation_outputs_immutable BEFORE UPDATE OR DELETE ON qa.conversation_outputs
    FOR EACH ROW EXECUTE FUNCTION retrieval.reject_raw_mutation();
CREATE TRIGGER conversation_threads_no_truncate BEFORE TRUNCATE ON qa.conversation_threads
    FOR EACH STATEMENT EXECUTE FUNCTION retrieval.reject_raw_mutation();
CREATE TRIGGER conversation_inputs_no_truncate BEFORE TRUNCATE ON qa.conversation_inputs
    FOR EACH STATEMENT EXECUTE FUNCTION retrieval.reject_raw_mutation();
CREATE TRIGGER conversation_outputs_no_truncate BEFORE TRUNCATE ON qa.conversation_outputs
    FOR EACH STATEMENT EXECUTE FUNCTION retrieval.reject_raw_mutation();
