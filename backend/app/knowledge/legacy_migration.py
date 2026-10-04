"""Read-only legacy snapshot planning, followed by an explicit atomic import."""

from dataclasses import dataclass, field
import json
from pathlib import Path, PureWindowsPath
import re
from typing import Any

from app.knowledge.contracts import content_hash
from app.knowledge.postgres import MigrationError


STATUSES = {"active", "draft", "pending", "revoked", "deleted", "archived", "superseded"}
TABLE_COLUMNS = {
    "source_records": (
        "tenant_id", "source_record_id", "source_version", "source_system", "external_id",
        "source_locator", "title", "raw_content", "content_hash", "access_scope",
        "lifecycle_status", "metadata",
    ),
    "documents": (
        "tenant_id", "document_id", "document_version", "source_record_id", "source_version",
        "filename", "storage_locator", "content_hash", "access_scope", "lifecycle_status", "metadata",
    ),
    "document_chunks": (
        "tenant_id", "chunk_id", "document_id", "document_version", "chunk_index", "body_text",
        "content_hash", "source_locator", "access_scope", "lifecycle_status", "metadata",
    ),
    "knowledge_units": (
        "tenant_id", "unit_id", "unit_version", "source_record_id", "source_version",
        "question", "answer", "content_hash", "access_scope", "lifecycle_status", "metadata",
    ),
}
TABLE_KEYS = {
    "source_records": ("tenant_id", "source_record_id", "source_version"),
    "documents": ("tenant_id", "document_id", "document_version"),
    "document_chunks": ("tenant_id", "chunk_id", "document_version"),
    "knowledge_units": ("tenant_id", "unit_id", "unit_version"),
}


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


@dataclass
class MigrationPlan:
    rows: dict[str, list[dict[str, Any]]] = field(
        default_factory=lambda: {table: [] for table in TABLE_COLUMNS}
    )
    errors: list[dict[str, str]] = field(default_factory=list)
    warnings: list[dict[str, str]] = field(default_factory=list)
    quarantined: list[dict[str, Any]] = field(default_factory=list)

    @property
    def snapshot_hash(self) -> str:
        ordered = {
            table: sorted(rows, key=lambda row: tuple(row[key] for key in TABLE_KEYS[table]))
            for table, rows in self.rows.items()
        }
        if self.quarantined:
            ordered["quarantined_legacy_records"] = sorted(self.quarantined, key=lambda r: (r["tenant_id"], r["payload_hash"]))
        return content_hash(canonical_json(ordered))

    def summary(self) -> dict[str, Any]:
        return {
            "mode": "preview", "ready_to_apply": not self.errors,
            "snapshot_hash": self.snapshot_hash,
            "counts": {table: len(rows) for table, rows in self.rows.items()},
            "errors": self.errors, "warnings": self.warnings,
            "quarantined_records": len(self.quarantined),
        }


class LegacySnapshotPlanner:
    def __init__(self, storage_root: Path, tenant_id: str = "default") -> None:
        self.root = storage_root.resolve()
        if not self.root.is_dir() or not tenant_id.strip():
            raise MigrationError("An existing storage root and nonempty tenant ID are required")
        self.tenant_id = tenant_id

    def build(self, *, include_seed: bool = True) -> MigrationPlan:
        plan = MigrationPlan()
        sources: dict[tuple[str, str], dict[str, Any]] = {}
        documents: dict[tuple[str, str], dict[str, Any]] = {}
        for label, raw in self._jsonl("source_records", plan):
            try:
                tenant = self._tenant(raw)
                source_id = self._required(raw, "source_record_id")
                text = str(raw.get("raw_content", ""))
                row = {
                    "tenant_id": tenant, "source_record_id": source_id,
                    "source_version": str(raw.get("source_version") or raw.get("source_updated_at") or content_hash(text)),
                    "source_system": self._required(raw, "source_system"),
                    "external_id": self._required(raw, "external_id"),
                    "source_locator": self._required(raw, "source_locator"),
                    "title": str(raw.get("title", "")), "raw_content": text,
                    "content_hash": content_hash(text), "access_scope": self._scope(raw),
                    "lifecycle_status": self._status(raw), "metadata": raw,
                }
                self._append(plan, "source_records", row, label)
                sources[(tenant, source_id)] = row
            except ValueError as error:
                self._error(plan, label, str(error))

        for label, raw in self._jsonl("documents", plan):
            try:
                tenant = self._tenant(raw)
                document_id = self._required(raw, "document_id")
                filename = self._required(raw, "filename")
                basename = PureWindowsPath(self._required(raw, "storage_path")).name
                path = self._confined(self.root / "uploads" / basename)
                if not path.is_file():
                    raise ValueError("missing_document_file")
                digest = content_hash(path.read_bytes())
                version = str(raw.get("document_version") or digest)
                locator = path.relative_to(self.root).as_posix()
                source = self._resolve_source(raw, tenant, sources)
                if source is None:
                    source = self._local_source(raw, tenant, f"legacy-document:{document_id}",
                                                version, locator, digest, filename)
                    self._append(plan, "source_records", source, label)
                    sources[(tenant, source["source_record_id"])] = source
                row = {
                    "tenant_id": tenant, "document_id": document_id, "document_version": version,
                    "source_record_id": source["source_record_id"], "source_version": source["source_version"],
                    "filename": filename, "storage_locator": locator, "content_hash": digest,
                    "access_scope": self._scope(raw, source["access_scope"]),
                    "lifecycle_status": self._status(raw), "metadata": raw,
                }
                self._append(plan, "documents", row, label)
                documents[(tenant, document_id)] = row
            except ValueError as error:
                allowed_codes = {
                    "missing_document_id", "missing_filename", "missing_storage_path", "missing_document_file",
                    "unconfined_file", "missing_source_record", "source_version_mismatch",
                    "conflicting_versioned_id", "invalid_status",
                }
                code = str(error) if str(error) in allowed_codes else "invalid_document_or_source_reference"
                self._error(plan, label, code)
            except OSError:
                self._error(plan, label, "unreadable_document_file")

        for label, raw in self._jsonl("chunks", plan):
            try:
                tenant = self._tenant(raw)
                chunk_id = self._required(raw, "chunk_id")
                document = documents.get((tenant, self._required(raw, "document_id")))
                if document is None:
                    raise ValueError("orphan_chunk")
                source_id = raw.get("source_record_id")
                if source_id and source_id != document["source_record_id"]:
                    raise ValueError("chunk_source_mismatch")
                if raw.get("document_version") and str(raw["document_version"]) != document["document_version"]:
                    raise ValueError("chunk_document_version_mismatch")
                text = self._required(raw, "text")
                index = int(raw.get("chunk_index", 0))
                if index < 0:
                    raise ValueError("invalid_chunk_index")
                self._append(plan, "document_chunks", {
                    "tenant_id": tenant, "chunk_id": chunk_id, "document_id": document["document_id"],
                    "document_version": document["document_version"], "chunk_index": index,
                    "body_text": text, "content_hash": content_hash(text),
                    "source_locator": str(raw.get("source_locator") or f"{document['storage_locator']}#chunk={index + 1}"),
                    "access_scope": self._scope(raw, document["access_scope"]),
                    "lifecycle_status": self._status(raw), "metadata": raw,
                }, label)
            except (ValueError, TypeError) as error:
                code = str(error) if isinstance(error, ValueError) and str(error) in {
                    "orphan_chunk", "chunk_source_mismatch", "chunk_document_version_mismatch",
                    "invalid_chunk_index", "invalid_status", "missing_text",
                } else "invalid_chunk"
                self._error(plan, label, code)

        faqs = self._faq_rows(plan, include_seed)
        for label, raw in faqs:
            try:
                tenant = self._tenant(raw)
                unit_id = self._required({"unit_id": raw.get("unit_id") or raw.get("id")}, "unit_id")
                question = self._required(raw, "question")
                answer = self._required(raw, "answer")
                text = question + "\n" + answer
                source = self._resolve_source(raw, tenant, sources)
                if source is None:
                    source = self._local_source(raw, tenant, f"legacy-faq:{unit_id}",
                                                content_hash(text), str(raw.get("source_locator") or unit_id),
                                                content_hash(text), str(raw.get("source_label") or "Legacy FAQ"), text)
                    self._append(plan, "source_records", source, label)
                    sources[(tenant, source["source_record_id"])] = source
                self._append(plan, "knowledge_units", {
                    "tenant_id": tenant, "unit_id": unit_id,
                    "unit_version": str(raw.get("unit_version") or raw.get("version") or "1"),
                    "source_record_id": source["source_record_id"], "source_version": source["source_version"],
                    "question": question, "answer": answer, "content_hash": content_hash(text),
                    "access_scope": self._scope(raw, source["access_scope"]),
                    "lifecycle_status": self._status(raw), "metadata": raw,
                }, label)
            except ValueError as error:
                self._error(plan, label, str(error))
        return plan

    def _faq_rows(self, plan: MigrationPlan, include_seed: bool) -> list[tuple[str, dict[str, Any]]]:
        rows: dict[tuple[str, str], tuple[str, dict[str, Any]]] = {}
        if include_seed:
            seed = self.root / "seed" / "mock_faq.json"
            if seed.exists():
                try:
                    payload = json.loads(self._confined(seed).read_text(encoding="utf-8"))
                    if not isinstance(payload, list):
                        raise ValueError
                    for index, raw in enumerate(payload):
                        self._faq_add(rows, f"seed/mock_faq.json:{index + 1}", raw, plan, latest=False)
                except (ValueError, OSError):
                    self._error(plan, "seed/mock_faq.json", "invalid_seed_json")
            for folder in ("seed", "uploads"):
                for path in sorted((self.root / folder).glob("*_faq_seed_*.md")):
                    try:
                        match = re.search(r"```json\s*(\[[\s\S]*?\])\s*```",
                                          self._confined(path).read_text(encoding="utf-8"))
                        if match is None:
                            continue
                        for index, raw in enumerate(json.loads(match.group(1))):
                            self._faq_add(rows, f"{folder}/{path.name}:{index + 1}", raw, plan, latest=False)
                    except (ValueError, OSError):
                        self._error(plan, f"{folder}/{path.name}", "invalid_seed_markdown")
        # Historical extracted JSONL is append/upsert data: the last canonical ID wins.
        for label, raw in self._jsonl("extracted_faqs", plan):
            self._faq_add(rows, label, raw, plan, latest=True)
        return list(rows.values())

    def _faq_add(self, rows: dict, label: str, raw: Any, plan: MigrationPlan, *, latest: bool) -> None:
        if not isinstance(raw, dict):
            self._error(plan, label, "invalid_faq_object")
            return
        try:
            canonical_json(raw)
        except (ValueError, TypeError):
            self._error(plan, label, "invalid_json_object")
            return
        key = (self._tenant(raw), str(raw.get("unit_id") or raw.get("id") or ""))
        if key in rows:
            previous = rows[key][1]
            # Seed precedence follows the existing repository. Extracted revisions preserve revocation.
            if not latest and previous != raw:
                self._error(plan, label, "conflicting_seed_faq_id")
                return
            plan.warnings.append({"location": label, "code": "duplicate_faq_id_collapsed"})
            if not latest:
                return
        rows[key] = (label, raw)

    def _jsonl(self, name: str, plan: MigrationPlan) -> list[tuple[str, dict[str, Any]]]:
        path = self.root / name / f"{name}.jsonl"
        if not path.exists():
            return []
        try:
            lines = self._confined(path).read_text(encoding="utf-8").splitlines()
        except (OSError, ValueError):
            self._error(plan, name, "unreadable_or_unconfined_file")
            return []
        rows = []
        for number, line in enumerate(lines, 1):
            if not line.strip():
                continue
            label = f"{name}/{name}.jsonl:{number}"
            try:
                raw = json.loads(line)
                if not isinstance(raw, dict):
                    raise ValueError
                canonical_json(raw)
                rows.append((label, raw))
            except ValueError:
                self._error(plan, label, "invalid_json_object")
        return rows

    def _confined(self, path: Path) -> Path:
        resolved = path.resolve()
        if not resolved.is_relative_to(self.root):
            raise ValueError("unconfined_file")
        return resolved

    def _tenant(self, raw: dict[str, Any]) -> str:
        return str(raw.get("tenant_id") or self.tenant_id)

    @staticmethod
    def _required(raw: dict[str, Any], key: str) -> str:
        value = raw.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"missing_{key}")
        return value

    @staticmethod
    def _scope(raw: dict[str, Any], fallback: str = "internal") -> str:
        return str(raw.get("access_scope") or fallback)

    @staticmethod
    def _status(raw: dict[str, Any]) -> str:
        status = str(raw.get("lifecycle_status") or raw.get("status") or "active")
        if status not in STATUSES:
            raise ValueError("invalid_status")
        return status

    @staticmethod
    def _resolve_source(raw: dict, tenant: str, sources: dict) -> dict | None:
        source_id = raw.get("source_record_id")
        if not source_id:
            return None
        source = sources.get((tenant, source_id))
        if source is None:
            raise ValueError("missing_source_record")
        if raw.get("source_version") and str(raw["source_version"]) != source["source_version"]:
            raise ValueError("source_version_mismatch")
        return source

    def _local_source(self, raw: dict, tenant: str, source_id: str, version: str,
                      locator: str, digest: str, title: str, text: str = "") -> dict:
        return {
            "tenant_id": tenant, "source_record_id": source_id, "source_version": version,
            "source_system": "legacy_local", "external_id": source_id, "source_locator": locator,
            "title": title, "raw_content": text, "content_hash": digest,
            "access_scope": self._scope(raw), "lifecycle_status": self._status(raw),
            "metadata": {"legacy_local_source": True},
        }

    @staticmethod
    def _append(plan: MigrationPlan, table: str, row: dict, label: str) -> None:
        key = tuple(row[column] for column in TABLE_KEYS[table])
        for existing in plan.rows[table]:
            if key == tuple(existing[column] for column in TABLE_KEYS[table]):
                if existing != row:
                    raise ValueError("conflicting_versioned_id")
                return
        plan.rows[table].append(row)

    @staticmethod
    def _error(plan: MigrationPlan, location: str, code: str) -> None:
        plan.errors.append({"location": location, "code": code})


def apply_legacy_snapshot(connection: Any, plan: MigrationPlan) -> str:
    if plan.errors:
        raise MigrationError("Legacy import blocked by preview errors; no data written")
    from psycopg.types.json import Jsonb

    snapshot_hash = plan.snapshot_hash
    batch_id = f"legacy-{snapshot_hash}"
    with connection.transaction():
        connection.execute("SELECT pg_advisory_xact_lock(hashtext('orionstack.legacy-import'))")
        if connection.execute(
            "SELECT batch_id FROM core.import_batches WHERE snapshot_hash = %s", (snapshot_hash,)
        ).fetchone():
            return "duplicate"
        for table, columns in TABLE_COLUMNS.items():
            keys = TABLE_KEYS[table]
            for row in plan.rows[table]:
                existing = connection.execute(
                    f"SELECT {', '.join(columns)} FROM core.{table} WHERE "
                    + " AND ".join(f"{key} = %s" for key in keys),
                    tuple(row[key] for key in keys),
                ).fetchone()
                if existing is not None:
                    if dict(zip(columns, existing)) != row:
                        raise MigrationError(f"Conflicting existing version in core.{table}; import rolled back")
                    continue
                connection.execute(
                    f"INSERT INTO core.{table} ({', '.join(columns)}) VALUES "
                    f"({', '.join('%s' for _ in columns)})",
                    tuple(Jsonb(row[column]) if column == "metadata" else row[column] for column in columns),
                )
        for row in plan.quarantined:
            connection.execute("""
                INSERT INTO core.quarantined_legacy_records
                    (tenant_id,payload_hash,unit_id,source_record_id,origin,payload,resolution)
                VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (tenant_id,payload_hash) DO NOTHING
            """, (row["tenant_id"],row["payload_hash"],row["unit_id"],row["source_record_id"],
                  row["origin"],Jsonb(row["payload"]),Jsonb(row["resolution"])))
        connection.execute(
            "INSERT INTO core.import_batches (batch_id, snapshot_hash, counts) VALUES (%s, %s, %s)",
            (batch_id, snapshot_hash, Jsonb({table: len(rows) for table, rows in plan.rows.items()})),
        )
    return "imported"
