from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from app.storage.models.source_record import SourceRecord


def parse_export_file(
    path: Path,
    source_system: str,
    export_batch_id: str,
    tenant_id: str = "default",
) -> list[SourceRecord]:
    suffix = path.suffix.lower()
    if suffix == ".json":
        items = json.loads(path.read_text(encoding="utf-8"))
    elif suffix == ".jsonl":
        items = []
        for line in path.read_text(encoding="utf-8").strip().split("\n"):
            line = line.strip()
            if line:
                items.append(json.loads(line))
    else:
        return []

    if not isinstance(items, list):
        items = [items]

    records: list[SourceRecord] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        records.append(_item_to_record(item, source_system, export_batch_id, tenant_id))
    return records


def _item_to_record(
    item: dict[str, Any],
    source_system: str,
    export_batch_id: str,
    tenant_id: str,
) -> SourceRecord:
    raw = item.get("raw_content", "") or json.dumps(item, ensure_ascii=False)
    external_id = item.get("external_id", "") or item.get("id", "")
    source_system_resolved = item.get("source_system", source_system)
    sr_id = item.get("source_record_id", "") or f"sr-{source_system_resolved}-{hashlib.sha256((external_id + raw).encode()).hexdigest()[:8]}"

    return SourceRecord(
        source_record_id=sr_id,
        tenant_id=item.get("tenant_id", tenant_id),
        source_system=source_system_resolved,
        source_object_type=item.get("source_object_type", "faq_doc"),
        external_id=external_id,
        source_locator=item.get("source_locator", ""),
        title=item.get("title", ""),
        raw_content=raw,
        content_hash=SourceRecord.compute_content_hash(raw),
        source_updated_at=item.get("source_updated_at", ""),
        export_batch_id=item.get("export_batch_id", export_batch_id),
        access_scope=item.get("access_scope", "internal"),
        status=item.get("status", "active"),
        synced_at=item.get("synced_at", ""),
    )
