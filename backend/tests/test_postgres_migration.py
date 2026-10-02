from contextlib import contextmanager
import copy
import importlib.util
import json
from pathlib import Path

import pytest

from app.config.core_settings import CoreSettings
from app.knowledge.contracts import content_hash
from app.knowledge.legacy_migration import LegacySnapshotPlanner, TABLE_COLUMNS, TABLE_KEYS, apply_legacy_snapshot
from app.knowledge.postgres import DatabaseUnavailable, MigrationError, PostgresDatabase, SchemaMigrator


def write_jsonl(root, folder, rows):
    path = root / folder / f"{folder}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def sample_storage(root):
    uploads = root / "uploads"
    uploads.mkdir(parents=True)
    (uploads / "doc-1_policy.md").write_bytes(b"policy\n")
    write_jsonl(root, "source_records", [{
        "source_record_id": "source-1", "tenant_id": "t1", "source_system": "wiki", "external_id": "policy-1",
        "source_updated_at": "2026-10-01T00:00:00Z", "source_locator": "wiki://policy-1",
        "raw_content": "policy", "content_hash": "legacy-short-hash", "status": "active", "access_scope": "internal",
    }])
    write_jsonl(root, "documents", [{
        "document_id": "doc-1", "tenant_id": "t1", "filename": "policy.md",
        "source_record_id": "source-1", "storage_path": r"C:\old-workspace\uploads\doc-1_policy.md",
        "lifecycle_status": "revoked",
    }])
    write_jsonl(root, "chunks", [{
        "chunk_id": "chunk-1", "document_id": "doc-1", "tenant_id": "t1", "text": "policy chunk",
        "chunk_index": 0, "source_record_id": "source-1", "lifecycle_status": "revoked",
    }])
    write_jsonl(root, "extracted_faqs", [{
        "id": "faq-1", "tenant_id": "t1", "source_record_id": "source-1", "question": "How?", "answer": "Apply.",
        "unit_version": 2, "lifecycle_status": "revoked",
    }])


def file_hashes(root):
    return {str(path.relative_to(root)): content_hash(path.read_bytes()) for path in root.rglob("*") if path.is_file()}


def test_preview_preserves_ids_versions_status_hashes_and_does_not_write(tmp_path):
    sample_storage(tmp_path)
    before = file_hashes(tmp_path)
    plan = LegacySnapshotPlanner(tmp_path).build(include_seed=False)
    assert not plan.errors
    assert plan.summary()["ready_to_apply"]
    assert file_hashes(tmp_path) == before
    source = plan.rows["source_records"][0]
    assert source["source_record_id"] == "source-1"
    assert source["source_version"] == "2026-10-01T00:00:00Z"
    assert source["content_hash"] == content_hash("policy")
    assert source["metadata"]["content_hash"] == "legacy-short-hash"
    document = plan.rows["documents"][0]
    assert document["storage_locator"] == "uploads/doc-1_policy.md"
    assert document["document_version"] == content_hash(b"policy\n")
    assert document["lifecycle_status"] == "revoked"
    assert plan.rows["document_chunks"][0]["chunk_id"] == "chunk-1"
    assert plan.rows["document_chunks"][0]["lifecycle_status"] == "revoked"
    assert plan.rows["knowledge_units"][0]["unit_id"] == "faq-1"
    assert plan.rows["knowledge_units"][0]["unit_version"] == "2"


def test_local_documents_get_real_file_provenance_without_hash_as_identity(tmp_path):
    sample_storage(tmp_path)
    rows = [{"document_id": document_id, "filename": "policy.md", "storage_path": "doc-1_policy.md"}
            for document_id in ("doc-1", "doc-2")]
    write_jsonl(tmp_path, "documents", rows)
    write_jsonl(tmp_path, "chunks", [])
    plan = LegacySnapshotPlanner(tmp_path).build(include_seed=False)
    assert not plan.errors
    assert plan.rows["documents"][0]["content_hash"] == plan.rows["documents"][1]["content_hash"]
    assert {row["source_record_id"] for row in plan.rows["documents"]} == {"legacy-document:doc-1", "legacy-document:doc-2"}


def test_missing_scope_inherits_restricted_source_and_document(tmp_path):
    sample_storage(tmp_path)
    source_path = tmp_path / "source_records/source_records.jsonl"
    raw = json.loads(source_path.read_text(encoding="utf-8"))
    raw["access_scope"] = "restricted"
    write_jsonl(tmp_path, "source_records", [raw])
    plan = LegacySnapshotPlanner(tmp_path).build(include_seed=False)
    assert not plan.errors
    assert plan.rows["documents"][0]["access_scope"] == "restricted"
    assert plan.rows["document_chunks"][0]["access_scope"] == "restricted"
    assert plan.rows["knowledge_units"][0]["access_scope"] == "restricted"


@pytest.mark.parametrize("folder,rows,code", [
    ("chunks", [{"chunk_id": "orphan", "document_id": "missing", "text": "x"}], "orphan_chunk"),
    ("chunks", [{"chunk_id": "other", "tenant_id": "other", "document_id": "doc-1", "text": "x"}], "orphan_chunk"),
    ("chunks", [{"chunk_id": "x", "tenant_id": "t1", "document_id": "doc-1", "text": "x", "source_record_id": "other"}], "chunk_source_mismatch"),
    ("chunks", [{"chunk_id": "x", "tenant_id": "t1", "document_id": "doc-1", "text": "x", "lifecycle_status": "nonsense"}], "invalid_status"),
    ("extracted_faqs", [{"unit_id": "x", "source_record_id": "missing", "question": "Q", "answer": "A"}], "missing_source_record"),
])
def test_bad_references_block_whole_import(tmp_path, folder, rows, code):
    sample_storage(tmp_path)
    write_jsonl(tmp_path, folder, rows)
    plan = LegacySnapshotPlanner(tmp_path).build(include_seed=False)
    assert code in {error["code"] for error in plan.errors}
    assert not plan.summary()["ready_to_apply"]
    connection = MemoryConnection()
    with pytest.raises(MigrationError, match="blocked"):
        apply_legacy_snapshot(connection, plan)
    assert connection.statements == []


def test_latest_canonical_faq_keeps_revocation_instead_of_historical_active(tmp_path):
    sample_storage(tmp_path)
    base = {"tenant_id": "t1", "source_record_id": "source-1", "question": "Q", "answer": "A"}
    write_jsonl(tmp_path, "extracted_faqs", [
        dict(base, id="faq-1", lifecycle_status="active"),
        dict(base, unit_id="faq-1", id="obsolete-id", lifecycle_status="revoked"),
    ])
    plan = LegacySnapshotPlanner(tmp_path).build(include_seed=False)
    assert not plan.errors
    assert len(plan.rows["knowledge_units"]) == 1
    assert plan.rows["knowledge_units"][0]["unit_id"] == "faq-1"
    assert plan.rows["knowledge_units"][0]["lifecycle_status"] == "revoked"
    assert plan.warnings[0]["code"] == "duplicate_faq_id_collapsed"


def test_missing_file_is_reported_instead_of_fabricating_provenance(tmp_path):
    sample_storage(tmp_path)
    (tmp_path / "uploads/doc-1_policy.md").unlink()
    plan = LegacySnapshotPlanner(tmp_path).build(include_seed=False)
    assert not plan.rows["documents"]
    assert plan.errors


def test_preview_confines_symlink_reads_to_storage_root(tmp_path):
    root = tmp_path / "storage"
    root.mkdir()
    sample_storage(root)
    outside = tmp_path / "outside.md"
    outside.write_text("private", encoding="utf-8")
    target = root / "uploads/doc-1_policy.md"
    target.unlink()
    try:
        target.symlink_to(outside)
    except OSError:
        pytest.skip("Symlinks unavailable on this host")
    plan = LegacySnapshotPlanner(root).build(include_seed=False)
    assert plan.errors
    assert not plan.rows["documents"]
    assert "private" not in str(plan.summary())


def test_malformed_json_never_prints_input_content(tmp_path):
    sample_storage(tmp_path)
    (tmp_path / "chunks/chunks.jsonl").write_text('{"text":"PRIVATE', encoding="utf-8")
    plan = LegacySnapshotPlanner(tmp_path).build(include_seed=False)
    assert plan.errors[0]["code"] == "invalid_json_object"
    assert "PRIVATE" not in str(plan.summary())


def test_snapshot_hash_is_order_independent_and_sensitive_to_lifecycle(tmp_path):
    sample_storage(tmp_path)
    plan = LegacySnapshotPlanner(tmp_path).build(include_seed=False)
    second = copy.deepcopy(plan)
    for rows in second.rows.values():
        rows.reverse()
    assert plan.snapshot_hash == second.snapshot_hash
    second.rows["knowledge_units"][0]["lifecycle_status"] = "active"
    assert plan.snapshot_hash != second.snapshot_hash


class Rows:
    def __init__(self, rows=()):
        self.rows = list(rows)
    def fetchone(self):
        return self.rows[0] if self.rows else None
    def fetchall(self):
        return self.rows


class MemoryConnection:
    """Transaction double for importer orchestration, not PostgreSQL SQL validation."""
    def __init__(self):
        self.tables = {table: {} for table in TABLE_COLUMNS}
        self.batches = {}
        self.schema_versions = {}
        self.statements = []
        self.rollbacks = 0

    @contextmanager
    def transaction(self):
        before = copy.deepcopy((self.tables, self.batches, self.schema_versions))
        try:
            yield
        except Exception:
            self.tables, self.batches, self.schema_versions = before
            self.rollbacks += 1
            raise

    def execute(self, sql, params=()):
        self.statements.append((sql, params))
        if sql.startswith("SELECT version, checksum"):
            return Rows(self.schema_versions.items())
        if sql.startswith("INSERT INTO core.schema_migrations"):
            self.schema_versions[params[0]] = params[1]
        elif sql.startswith("SELECT batch_id"):
            return Rows([(self.batches[params[0]],)]) if params[0] in self.batches else Rows()
        elif sql.startswith("INSERT INTO core.import_batches"):
            self.batches[params[1]] = params[0]
        elif sql.startswith("SELECT") and " FROM core." in sql:
            table = sql.split(" FROM core.")[1].split()[0]
            row = self.tables[table].get(tuple(params))
            return Rows([tuple(row[column] for column in TABLE_COLUMNS[table])]) if row else Rows()
        elif sql.startswith("INSERT INTO core."):
            table = sql.split("INSERT INTO core.")[1].split()[0]
            values = [getattr(value, "obj", value) for value in params]
            row = dict(zip(TABLE_COLUMNS[table], values))
            self.tables[table][tuple(row[key] for key in TABLE_KEYS[table])] = row
        return Rows()


def test_atomic_import_is_idempotent_and_conflicts_roll_back(tmp_path):
    sample_storage(tmp_path)
    plan = LegacySnapshotPlanner(tmp_path).build(include_seed=False)
    connection = MemoryConnection()
    assert apply_legacy_snapshot(connection, plan) == "imported"
    committed = copy.deepcopy(connection.tables)
    assert apply_legacy_snapshot(connection, plan) == "duplicate"
    assert connection.tables == committed
    conflicting = copy.deepcopy(plan)
    extra = copy.deepcopy(plan.rows["source_records"][0])
    extra["source_record_id"] = "new-source"
    conflicting.rows["source_records"].insert(0, extra)
    conflicting.rows["knowledge_units"][0]["answer"] = "conflicting answer"
    with pytest.raises(MigrationError, match="Conflicting existing version"):
        apply_legacy_snapshot(connection, conflicting)
    assert connection.tables == committed
    assert len(connection.batches) == 1
    assert connection.rollbacks == 1


def test_schema_checksum_is_portable_and_changes_cannot_reapply(tmp_path):
    file = tmp_path / "001_example.sql"
    file.write_bytes(b"SELECT 1;\r\n")
    migrator = SchemaMigrator(tmp_path)
    checksum = migrator.migrations()[0].checksum
    connection = MemoryConnection()
    assert migrator.apply(connection) == ("001_example",)
    file.write_bytes(b"SELECT 1;\n")
    assert migrator.migrations()[0].checksum == checksum
    assert migrator.apply(connection) == ()
    file.write_bytes(b"SELECT 2;\n")
    with pytest.raises(MigrationError, match="checksum mismatch"):
        migrator.apply(connection)
    assert connection.schema_versions["001_example"] == checksum


def test_driver_failure_does_not_expose_database_password(monkeypatch):
    import psycopg
    def connect(*args, **kwargs):
        raise psycopg.OperationalError("postgresql://user:SECRET_PASSWORD@localhost/database")
    monkeypatch.setattr(psycopg, "connect", connect)
    with pytest.raises(DatabaseUnavailable) as error:
        with PostgresDatabase(CoreSettings(database_url="postgresql://unused")).connection():
            pytest.fail("Must fail before yielding")
    assert "SECRET_PASSWORD" not in str(error.value)


def test_cli_preview_needs_no_database_and_apply_errors_precede_connection(tmp_path, monkeypatch, capsys):
    sample_storage(tmp_path)
    script = Path(__file__).resolve().parents[2] / "scripts/migrate-postgres.py"
    spec = importlib.util.spec_from_file_location("postgres_cli", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    def fail_connection(*args, **kwargs):
        pytest.fail("Preview or invalid import must not connect to a database")
    monkeypatch.setattr(module.PostgresDatabase, "connection", fail_connection)
    monkeypatch.setattr("sys.argv", [str(script), "--storage-root", str(tmp_path), "--no-seed"])
    assert module.main() == 0
    assert json.loads(capsys.readouterr().out)["mode"] == "preview"
    write_jsonl(tmp_path, "extracted_faqs", [{"unit_id": "x", "question": "Q", "answer": "A", "source_record_id": "missing"}])
    monkeypatch.setattr("sys.argv", [str(script), "--storage-root", str(tmp_path), "--no-seed", "--apply"])
    assert module.main() == 2
    output = capsys.readouterr()
    assert "no database writes" in output.err
