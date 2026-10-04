-- User signals remain separate from immutable raw and confirmed training labels.
ALTER TABLE qa.workbench_runs ADD CONSTRAINT workbench_run_event_identity
    UNIQUE (tenant_id,id,retrieval_event_id);
CREATE TABLE qa.user_feedback (
    tenant_id text NOT NULL,
    id text NOT NULL,
    request_id text NOT NULL,
    actor_user_id text NOT NULL,
    idempotency_key text NOT NULL,
    payload_hash text NOT NULL CHECK (payload_hash ~ '^[0-9a-f]{64}$'),
    event_id text,
    candidate_id text,
    kind text NOT NULL CHECK (kind IN ('answer_helpfulness','candidate_relevance','factual_correction')),
    value text NOT NULL,
    comment text NOT NULL DEFAULT '',
    origin text NOT NULL CHECK (origin IN ('user_submission','automated_test')),
    evaluator text NOT NULL DEFAULT 'user_feedback' CHECK (evaluator='user_feedback'),
    review_state text NOT NULL DEFAULT 'unreviewed' CHECK (review_state='unreviewed'),
    training_eligible boolean NOT NULL DEFAULT false CHECK (NOT training_eligible),
    policy_version text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (tenant_id,id),
    UNIQUE (tenant_id,actor_user_id,idempotency_key),
    FOREIGN KEY (tenant_id,request_id) REFERENCES qa.workbench_runs (tenant_id,id),
    FOREIGN KEY (tenant_id,request_id,event_id) REFERENCES qa.workbench_runs (tenant_id,id,retrieval_event_id),
    FOREIGN KEY (tenant_id,event_id,candidate_id) REFERENCES retrieval.retrieval_candidate (tenant_id,event_id,id),
    CHECK ((kind='answer_helpfulness' AND value IN ('helpful','not_helpful') AND candidate_id IS NULL)
        OR (kind='candidate_relevance' AND value IN ('relevant','not_relevant') AND candidate_id IS NOT NULL AND event_id IS NOT NULL)
        OR (kind='factual_correction' AND value='correction' AND btrim(comment)<>'')),
    CHECK (candidate_id IS NULL OR event_id IS NOT NULL)
);
CREATE INDEX user_feedback_run ON qa.user_feedback (tenant_id,request_id,created_at,id);
CREATE TRIGGER user_feedback_immutable BEFORE UPDATE OR DELETE ON qa.user_feedback
    FOR EACH ROW EXECUTE FUNCTION retrieval.reject_raw_mutation();
CREATE TRIGGER user_feedback_no_truncate BEFORE TRUNCATE ON qa.user_feedback
    FOR EACH STATEMENT EXECUTE FUNCTION retrieval.reject_raw_mutation();

CREATE TABLE qa.authorization_events (
    tenant_id text NOT NULL,
    id text NOT NULL,
    principal_id text NOT NULL,
    action text NOT NULL,
    resource_id text NOT NULL,
    decision text NOT NULL CHECK (decision IN ('allow','deny')),
    policy_version text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (tenant_id,id)
);
CREATE INDEX qa_authorization_actor ON qa.authorization_events (tenant_id,principal_id,resource_id,created_at);
CREATE TRIGGER qa_authorization_immutable BEFORE UPDATE OR DELETE ON qa.authorization_events
    FOR EACH ROW EXECUTE FUNCTION retrieval.reject_raw_mutation();
CREATE TRIGGER qa_authorization_no_truncate BEFORE TRUNCATE ON qa.authorization_events
    FOR EACH STATEMENT EXECUTE FUNCTION retrieval.reject_raw_mutation();

-- Domain outcomes and evaluations are additional facts, never in-place edits.
CREATE TRIGGER answer_run_immutable BEFORE UPDATE OR DELETE ON retrieval.answer_runs
    FOR EACH ROW EXECUTE FUNCTION retrieval.reject_raw_mutation();
CREATE TRIGGER answer_run_no_truncate BEFORE TRUNCATE ON retrieval.answer_runs
    FOR EACH STATEMENT EXECUTE FUNCTION retrieval.reject_raw_mutation();
CREATE TRIGGER evaluation_immutable BEFORE UPDATE OR DELETE ON retrieval.retrieval_evaluation
    FOR EACH ROW EXECUTE FUNCTION retrieval.reject_raw_mutation();
CREATE TRIGGER evaluation_no_truncate BEFORE TRUNCATE ON retrieval.retrieval_evaluation
    FOR EACH STATEMENT EXECUTE FUNCTION retrieval.reject_raw_mutation();
CREATE TRIGGER processing_run_immutable BEFORE UPDATE OR DELETE ON retrieval.processing_run
    FOR EACH ROW EXECUTE FUNCTION retrieval.reject_raw_mutation();
CREATE TRIGGER processing_run_no_truncate BEFORE TRUNCATE ON retrieval.processing_run
    FOR EACH STATEMENT EXECUTE FUNCTION retrieval.reject_raw_mutation();
CREATE TRIGGER processing_result_immutable BEFORE UPDATE OR DELETE ON retrieval.processing_result
    FOR EACH ROW EXECUTE FUNCTION retrieval.reject_raw_mutation();
CREATE TRIGGER processing_result_no_truncate BEFORE TRUNCATE ON retrieval.processing_result
    FOR EACH STATEMENT EXECUTE FUNCTION retrieval.reject_raw_mutation();

