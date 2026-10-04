-- Missing historical configuration is unknown; never backfill it with current state.
ALTER TABLE retrieval.retrieval_event ADD COLUMN runtime_versions jsonb NOT NULL DEFAULT '{}';
