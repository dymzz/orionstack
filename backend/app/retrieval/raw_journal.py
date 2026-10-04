"""PostgreSQL journal: raw facts and downstream results have separate writes."""

import json

from app.knowledge.contracts import AccessContext
from app.knowledge.postgres import PostgresDatabase
from app.retrieval.raw_contracts import (
    ProcessingRun, RawCandidate, RawRetrievalEvent, RawRetrievalRecord, RetrievalEvaluation, RetrievalResponse,
)


class PostgresRawJournal:
    def __init__(self, database: PostgresDatabase | None = None) -> None:
        self.database = database or PostgresDatabase()

    def record_raw(self, connection, record: RawRetrievalRecord, access: AccessContext) -> None:
        from psycopg.types.json import Jsonb
        record.require_access(access)
        event = record.event
        # Candidate FKs are deferred: the event is inserted last and seals the set.
        for candidate in record.candidates:
            connection.execute("""
                INSERT INTO retrieval.retrieval_candidate
                    (tenant_id, event_id, id, document_id, document_version, chunk_id,
                     content_hash, rank, similarity_score, raw_snapshot, snapshot_hash)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (event.tenant_id, event.id, candidate.candidate_id, candidate.document_id,
                  candidate.document_version, candidate.chunk_id, candidate.content_hash, candidate.rank,
                  candidate.similarity_score, Jsonb(candidate.model_dump(mode="json")), candidate.snapshot_hash))
        connection.execute("""
            INSERT INTO retrieval.retrieval_event
                (tenant_id, id, user_id, query, query_hash, embedding_signature, embedding_configuration,
                 query_vector, document_ids, allowed_scopes, top_k, candidate_count, retrieval_method, created_at,runtime_versions)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,%s)
        """, (event.tenant_id, event.id, event.user_id, event.query, event.query_hash,
              event.embedding_signature, Jsonb(event.embedding_configuration.model_dump()),
              Jsonb(list(event.query_vector)), Jsonb(list(event.document_ids)), Jsonb(list(event.allowed_scopes)),
              event.top_k, event.candidate_count, event.retrieval_method, event.created_at,Jsonb(event.runtime_versions.model_dump())))

    def save_processing(self, record: RawRetrievalRecord, run: ProcessingRun, access: AccessContext) -> None:
        from psycopg.types.json import Jsonb
        record.require_access(access)
        RetrievalResponse(raw=record, processing=run)  # membership check before DB writes
        if self.load_raw(record.event.id, access) != record:
            raise ValueError("Processing input differs from the persisted raw retrieval record")
        with self.database.connection() as connection:
            with connection.transaction():
                # Verify ownership on the actual persisted event, not just caller fields.
                row = connection.execute(
                    "SELECT user_id FROM retrieval.retrieval_event WHERE tenant_id = %s AND id = %s",
                    (access.tenant_id, record.event.id),
                ).fetchone()
                if row is None or (row[0] != access.user_id and "admin" not in access.roles):
                    raise PermissionError("Persisted retrieval event is not accessible")
                connection.execute("""
                    INSERT INTO retrieval.processing_run
                        (tenant_id, event_id, id, policy, status, error_code, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (access.tenant_id, record.event.id, run.id,
                      Jsonb({"processors": list(run.processors), "final_top_k": run.final_top_k,
                             "configuration": json.loads(run.configuration_json)}),
                      run.status, run.error_code, run.created_at))
                for evaluation in run.evaluations:
                    connection.execute("""
                        INSERT INTO retrieval.retrieval_evaluation
                            (tenant_id, event_id, id, candidate_id, processing_run_id, evaluator,
                             evaluator_version, decision, score, reason, details, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (access.tenant_id, record.event.id, evaluation.id, evaluation.candidate_id, run.id,
                          evaluation.evaluator, evaluation.evaluator_version, evaluation.decision,
                          evaluation.score, evaluation.reason, Jsonb(json.loads(evaluation.details_json)),
                          evaluation.created_at))
                for rank, candidate_id in enumerate(run.selected_candidate_ids, 1):
                    connection.execute("""
                        INSERT INTO retrieval.processing_result
                            (tenant_id, event_id, processing_run_id, candidate_id, rank)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (access.tenant_id, record.event.id, run.id, candidate_id, rank))

    def append_evaluations(self, event_id: str, evaluations: tuple[RetrievalEvaluation, ...],
                           access: AccessContext) -> None:
        """Append authenticated feedback independently of an online processing run."""
        from psycopg.types.json import Jsonb
        record = self.load_raw(event_id, access)
        candidate_ids = {candidate.candidate_id for candidate in record.candidates}
        for evaluation in evaluations:
            if evaluation.evaluator not in {"human", "user_feedback", "known_answer"}:
                raise ValueError("Feedback must identify human, user_feedback or known_answer provenance")
            if evaluation.evaluator != "user_feedback" and "admin" not in access.roles:
                raise PermissionError("Curator permission is required for reviewed labels")
            if evaluation.candidate_id is not None and evaluation.candidate_id not in candidate_ids:
                raise ValueError("Feedback candidate does not belong to this retrieval event")
        with self.database.connection() as connection:
            with connection.transaction():
                for evaluation in evaluations:
                    connection.execute("""
                        INSERT INTO retrieval.retrieval_evaluation
                            (tenant_id, event_id, id, candidate_id, evaluator, evaluator_version,
                             decision, score, reason, details, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (access.tenant_id, event_id, evaluation.id, evaluation.candidate_id,
                          evaluation.evaluator, evaluation.evaluator_version, evaluation.decision,
                          evaluation.score, evaluation.reason,
                          Jsonb({**json.loads(evaluation.details_json), "actor_user_id": access.user_id}),
                          evaluation.created_at))

    def load_raw(self, event_id: str, access: AccessContext) -> RawRetrievalRecord:
        from psycopg.rows import dict_row
        with self.database.connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                row = cursor.execute("""
                    SELECT * FROM retrieval.retrieval_event WHERE tenant_id = %s AND id = %s
                """, (access.tenant_id, event_id)).fetchone()
                if row is None or (row["user_id"] != access.user_id and "admin" not in access.roles):
                    raise PermissionError("Raw retrieval event is not accessible")
                rows = cursor.execute("""
                    SELECT * FROM retrieval.retrieval_candidate
                    WHERE tenant_id = %s AND event_id = %s ORDER BY rank
                """, (access.tenant_id, event_id)).fetchall()
        fields = {key: value for key, value in row.items() if key != "embedding_signature"}
        event = RawRetrievalEvent.model_validate(fields)
        if event.embedding_signature != row["embedding_signature"]:
            raise ValueError("Stored embedding configuration fingerprint mismatch")
        candidates = []
        for stored in rows:
            candidate = RawCandidate.model_validate(stored["raw_snapshot"])
            if (candidate.snapshot_hash != stored["snapshot_hash"]
                    or any(getattr(candidate, key) != stored[key] for key in
                           ("document_id", "document_version", "chunk_id", "content_hash", "rank", "similarity_score"))
                    or candidate.candidate_id != stored["id"]):
                raise ValueError("Stored raw candidate snapshot mismatch")
            candidates.append(candidate)
        record = RawRetrievalRecord(event=event, candidates=tuple(candidates))
        record.require_access(access)
        return record
