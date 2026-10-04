"""Reviewed quarantine is explicit and hash-bound; it never invents a source."""

import json
from pathlib import Path

from app.knowledge.contracts import content_hash
from app.knowledge.legacy_migration import canonical_json
from app.knowledge.postgres import MigrationError


def resolve_missing_sources(plan, storage_root: Path, manifest_path: Path, *, fallback_tenant: str = "default") -> None:
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        entries = manifest["resolutions"]
        if manifest["schema_version"] != 1 or not isinstance(entries, list):
            raise ValueError
        lines = (storage_root / "extracted_faqs/extracted_faqs.jsonl").read_text(encoding="utf-8").splitlines()
        rows = [(number, json.loads(line)) for number, line in enumerate(lines, 1) if line.strip()]
        if any(not isinstance(row, dict) for _, row in rows):
            raise ValueError
        def identity(row):
            return str(row.get("tenant_id") or fallback_tenant), row.get("unit_id") or row.get("id")
        latest = {identity(row): (number, row) for number, row in rows}
        handled = set()
        quarantined = []
        errors = list(plan.errors)
        warnings = []
        for resolution in entries:
            key = (resolution["tenant_id"], resolution["unit_id"])
            number, current = latest[key]
            origin = f"extracted_faqs/extracted_faqs.jsonl:{number}"
            if (key in handled or resolution["operation"] != "quarantine"
                    or not resolution["reason"].strip() or not resolution["evidence"].strip()
                    or content_hash(canonical_json(current)) != resolution["expected_payload_hash"]
                    or current.get("source_record_id") != resolution["source_record_id"]
                    or {"location": origin, "code": "missing_source_record"} not in errors):
                raise ValueError
            handled.add(key)
            for history_number, row in rows:
                if identity(row) == key:
                    quarantined.append({
                        "tenant_id": key[0], "unit_id": key[1], "source_record_id": row["source_record_id"],
                        "origin": f"extracted_faqs/extracted_faqs.jsonl:{history_number}", "payload": row,
                        "payload_hash": content_hash(canonical_json(row)), "resolution": resolution,
                    })
            errors.remove({"location": origin, "code": "missing_source_record"})
            warnings.append({"location": origin, "code": "explicitly_quarantined_missing_source"})
        # Do not partially relax a plan if a later manifest entry fails validation.
        plan.quarantined.extend(quarantined)
        plan.errors[:] = errors
        plan.warnings.extend(warnings)
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        raise MigrationError("Legacy resolution manifest does not match the current missing-source records") from None
