"""PostgreSQL SQL semantics in isolated PGlite, through the Python repositories."""

from contextlib import contextmanager
from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

from app.knowledge.contracts import AccessContext, QueryContext, content_hash
from app.knowledge.embedding import EmbeddingBatch, EmbeddingSignature
from app.knowledge.postgres import SchemaMigrator
from app.retrieval.postgres_vector import EmbeddingWriteConflict, PostgresEmbeddingRepository, PostgresVectorRetriever
from app.retrieval.raw_journal import PostgresRawJournal
from app.retrieval.raw_pipeline import RawRetrievalPipeline
from app.retrieval.raw_contracts import RetrievalEvaluation
from app.retrieval.training import ApprovedLabel, PostgresTrainingRepository, derive_training_example

HARNESS = Path(__file__).resolve().parents[2] / "postgres-test-harness"


class SqlFailure(RuntimeError):
    def __init__(self, message, code):
        super().__init__(message)
        self.code = code


class Result:
    def __init__(self, response, as_dict):
        self.rows = response["rows"] if as_dict else [tuple(row.get(key) for key in response["fields"]) for row in response["rows"]]
        self.rowcount = response["rowcount"]
    def fetchone(self): return self.rows[0] if self.rows else None
    def fetchall(self): return self.rows


class Cursor:
    def __init__(self, bridge): self.bridge = bridge
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def execute(self, sql, params=()): return self.bridge.execute(sql, params, as_dict=True)


class Bridge:
    def __init__(self):
        self.process = subprocess.Popen(
            [shutil.which("node"), str(HARNESS / "bridge.mjs")], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8",
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        self.depth = 0

    def execute(self, sql, params=(), *, as_dict=False):
        def encode(value):
            if hasattr(value, "obj"): return value.obj
            if isinstance(value, datetime): return value.isoformat()
            if isinstance(value, bytes): return {"__bytea_hex": value.hex()}
            raise TypeError(type(value).__name__)
        pieces = sql.split("%s")
        sql = "".join(piece + (f"${index + 1}" if index < len(pieces) - 1 else "") for index, piece in enumerate(pieces))
        request = {"sql": sql, "params": list(params)}
        if len(pieces) == 1 and sql.lstrip().startswith(("--", "CREATE", "ALTER")):
            request["exec"] = True
        self.process.stdin.write(json.dumps(request, default=encode, ensure_ascii=False) + "\n")
        self.process.stdin.flush()
        line = self.process.stdout.readline()
        if not line: raise RuntimeError("PostgreSQL harness terminated: " + self.process.stderr.read())
        response = json.loads(line, object_hook=lambda value: bytes.fromhex(value["__bytea_hex"])
                              if set(value) == {"__bytea_hex"} else value)
        if "error" in response: raise SqlFailure(response["error"], response.get("code"))
        return Result(response, as_dict)

    def cursor(self, **kwargs): return Cursor(self)

    @contextmanager
    def transaction(self):
        depth = self.depth
        self.execute("BEGIN" if depth == 0 else f"SAVEPOINT bridge_{depth}")
        self.depth += 1
        try:
            yield
            self.execute("COMMIT" if depth == 0 else f"RELEASE SAVEPOINT bridge_{depth}")
        except Exception:
            self.execute("ROLLBACK" if depth == 0 else f"ROLLBACK TO SAVEPOINT bridge_{depth}")
            raise
        finally:
            self.depth -= 1

    def close(self):
        self.process.stdin.write('{"close":true}\n')
        self.process.stdin.flush()
        self.process.communicate(timeout=20)


class Database:
    def __init__(self, bridge): self.bridge = bridge
    @contextmanager
    def connection(self): yield self.bridge


@pytest.fixture
def database():
    if not shutil.which("node") or not (HARNESS / "node_modules/@electric-sql/pglite/package.json").exists():
        pytest.skip("Install isolated SQL test dependencies: npm ci --prefix postgres-test-harness")
    bridge = Bridge()
    try:
        assert SchemaMigrator().apply(bridge) == tuple(m.version for m in SchemaMigrator().migrations())
        assert SchemaMigrator().apply(bridge) == ()
        yield Database(bridge)
    finally:
        bridge.close()


def seed(bridge, signature):
    for tenant, suffix, scope, status in (
        ("t1", "bad", "internal", "active"), ("t1", "good", "internal", "active"),
        ("other", "foreign", "internal", "active"), ("t1", "restricted", "restricted", "active"),
        ("t1", "revoked", "internal", "revoked"),
    ):
        text = "Unrelated passage" if suffix == "bad" else "Medical certificate is required"
        digest = content_hash(text)
        bridge.execute("""INSERT INTO core.source_records
            (tenant_id, source_record_id, source_version, source_system, external_id, source_locator,
             raw_content, content_hash, access_scope, lifecycle_status)
            VALUES (%s, %s, 'v1', 'demo', %s, 'demo://policy', %s, %s, %s, %s)
        """, (tenant, suffix, suffix, text, digest, scope, status))
        bridge.execute("""INSERT INTO core.documents
            (tenant_id, document_id, document_version, source_record_id, source_version,
             filename, storage_locator, content_hash, access_scope, lifecycle_status)
            VALUES (%s, %s, 'v1', %s, 'v1', 'demo.md', 'demo.md', %s, 'internal', 'active')
        """, (tenant, suffix, suffix, digest))
        bridge.execute("""INSERT INTO core.document_chunks
            (tenant_id, chunk_id, document_id, document_version, chunk_index, body_text, content_hash,
             source_locator, access_scope, lifecycle_status, embedding, embedding_model,
             embedding_dimensions, embedding_content_hash, embedding_signature)
            VALUES (%s, %s, %s, 'v1', 0, %s, %s, 'demo.md#1', 'internal', 'active', %s::vector, %s, 2, %s, %s)
        """, (tenant, suffix, suffix, text, digest, "[0.8,0.6]" if suffix == "good" else "[1,0]",
              signature.model, digest, signature.fingerprint))


def test_pgvector_permissions_raw_immutability_processing_and_training(database):
    bridge = database.bridge
    signature = EmbeddingSignature(model="@cf/baai/bge-m3", revision="test", dimensions=2)
    seed(bridge, signature)
    access = AccessContext(tenant_id="t1", user_id="u1")
    context = QueryContext(query="Sick leave documents?")
    batch = EmbeddingBatch(signature=signature, vectors=((1.0, 0.0),), input_hashes=(content_hash(context.query),))
    journal = PostgresRawJournal(database)
    retriever = PostgresVectorRetriever(database, journal)
    raw = retriever.retrieve_and_record(context, access, batch)
    assert [candidate.chunk_id for candidate in raw.candidates] == ["bad", "good"]
    assert [candidate.similarity_score for candidate in raw.candidates] == pytest.approx([1.0, 0.8])
    assert journal.load_raw(raw.event.id, access) == raw

    scope_context = QueryContext(query=context.query, document_ids=("good", "restricted", "revoked", "foreign"))
    scoped = retriever.retrieve_and_record(scope_context, access, batch)
    assert [candidate.chunk_id for candidate in scoped.candidates] == ["good"]
    mismatch = batch.model_copy(update={"signature": signature.model_copy(update={"revision": "different"})})
    empty = retriever.retrieve_and_record(context, access, mismatch)
    assert not empty.candidates
    assert journal.load_raw(empty.event.id, access) == empty

    for sql in (
        "UPDATE retrieval.retrieval_candidate SET similarity_score = 0",
        "UPDATE retrieval.retrieval_event SET query = 'rewritten'",
        "DELETE FROM retrieval.retrieval_candidate", "DELETE FROM retrieval.retrieval_event",
        "TRUNCATE retrieval.retrieval_candidate CASCADE", "TRUNCATE retrieval.retrieval_event CASCADE",
    ):
        with pytest.raises(SqlFailure, match="immutable"):
            with bridge.transaction(): bridge.execute(sql)
    assert journal.load_raw(raw.event.id, access) == raw

    with pytest.raises(SqlFailure, match="sealed"):
        with bridge.transaction():
            bridge.execute("""INSERT INTO retrieval.retrieval_candidate
                SELECT tenant_id, event_id, 'late', document_id, document_version, 'late', content_hash,
                       99, similarity_score, raw_snapshot, snapshot_hash
                FROM retrieval.retrieval_candidate WHERE event_id = %s LIMIT 1
            """, (raw.event.id,))
    with pytest.raises(SqlFailure, match="incomplete"):
        with bridge.transaction():
            bridge.execute("""INSERT INTO retrieval.retrieval_event
                SELECT tenant_id, 'incomplete', user_id, query, query_hash, embedding_signature,
                       embedding_configuration, query_vector, document_ids, allowed_scopes, top_k,
                       1, retrieval_method, created_at FROM retrieval.retrieval_event WHERE id = %s
            """, (raw.event.id,))

    from app.decision.retrieval_processors import ScoreRerankProcessor
    service = RawRetrievalPipeline(retriever=retriever, journal=journal,
                                   processors=(ScoreRerankProcessor(lambda query, texts: (0.1, 0.9), "test-reranker"),))
    response = service.process(raw, access, final_top_k=1)
    assert response.final_candidates[0].chunk_id == "good"
    assert journal.load_raw(raw.event.id, access) == raw
    assert bridge.execute("SELECT count(*) FROM retrieval.retrieval_evaluation").fetchone()[0] == 2
    assert bridge.execute("SELECT count(*) FROM retrieval.processing_result").fetchone()[0] == 1

    curator = access.model_copy(update={"roles": ("admin",)})
    feedback = RetrievalEvaluation(candidate_id=raw.candidates[0].candidate_id, evaluator="user_feedback",
                                   evaluator_version="v1", decision="negative", reason="Not about sick leave")
    journal.append_evaluations(raw.event.id, (feedback,), access)
    review = RetrievalEvaluation(candidate_id=raw.candidates[1].candidate_id, evaluator="human",
                                 evaluator_version="v1", decision="positive")
    with pytest.raises(PermissionError): journal.append_evaluations(raw.event.id, (review,), access)
    with pytest.raises(ValueError):
        journal.append_evaluations(raw.event.id, (feedback.model_copy(update={"candidate_id": "forged"}),), access)
    journal.append_evaluations(raw.event.id, (review,), curator)
    assert bridge.execute("SELECT count(*) FROM retrieval.retrieval_evaluation WHERE processing_run_id IS NULL").fetchone()[0] == 2
    assert journal.load_raw(raw.event.id, access) == raw
    labels = (ApprovedLabel(candidate_id=raw.candidates[1].candidate_id, label="positive", evaluator="human",
                            provenance_id="review-positive", approved=True),
              ApprovedLabel(candidate_id=raw.candidates[0].candidate_id, label="negative", evaluator="human",
                            provenance_id="review-negative", approved=True))
    example = derive_training_example(raw, curator, "dataset-1", labels)
    PostgresTrainingRepository(database).save(raw, example, curator)
    assert bridge.execute("SELECT count(*) FROM retrieval.training_example").fetchone()[0] == 1
    assert journal.load_raw(raw.event.id, access) == raw

    for wrong_access in (AccessContext(tenant_id="other", user_id="u1"),
                         AccessContext(tenant_id="t1", user_id="different")):
        with pytest.raises(PermissionError): journal.load_raw(raw.event.id, wrong_access)

    embeddings = PostgresEmbeddingRepository(database)
    pending = embeddings.pending_chunks(access, signature.model_copy(update={"revision": "next"}))
    assert {row["chunk_id"] for row in pending} == {"bad", "good"}
    replacement = EmbeddingBatch(signature=signature.model_copy(update={"revision": "next"}),
                                 vectors=((1.0, 0.0), (0.0, 1.0)),
                                 input_hashes=tuple(row["content_hash"] for row in pending))
    bridge.execute("UPDATE core.document_chunks SET lifecycle_status='revoked' WHERE chunk_id='good'")
    with pytest.raises(EmbeddingWriteConflict): embeddings.save_batch(access, pending, replacement)
    assert bridge.execute("SELECT embedding_signature FROM core.document_chunks WHERE chunk_id='bad'").fetchone()[0] == signature.fingerprint
