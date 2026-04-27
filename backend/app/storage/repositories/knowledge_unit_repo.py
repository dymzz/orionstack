from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class KnowledgeUnit:
    unit_id: str
    source_kind: str
    question: str
    answer: str
    body_text: str
    keywords: tuple[str, ...]
    business_domain: str
    document_type: str
    source_type: str
    source_label: str
    source_locator: str
    access_scope: str
    lifecycle_status: str
    valid_from: str
    valid_until: str | None
    version: str
    created_at: str
    tenant_id: str = "default"
    source_record_id: str | None = None
    unit_version: int = 1
    fresh_until: str | None = None
    stale_after: str | None = None
    import_batch_id: str | None = None
    published_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "unit_id": self.unit_id,
            "source_kind": self.source_kind,
            "question": self.question,
            "answer": self.answer,
            "body_text": self.body_text,
            "keywords": list(self.keywords),
            "business_domain": self.business_domain,
            "document_type": self.document_type,
            "source_type": self.source_type,
            "source_label": self.source_label,
            "source_locator": self.source_locator,
            "access_scope": self.access_scope,
            "lifecycle_status": self.lifecycle_status,
            "valid_from": self.valid_from,
            "valid_until": self.valid_until,
            "version": self.version,
            "created_at": self.created_at,
            "tenant_id": self.tenant_id,
            "source_record_id": self.source_record_id,
            "unit_version": self.unit_version,
            "fresh_until": self.fresh_until,
            "stale_after": self.stale_after,
            "import_batch_id": self.import_batch_id,
            "published_at": self.published_at,
        }

    def to_elasticsearch_doc(self) -> dict[str, Any]:
        return {
            "unit_id": self.unit_id,
            "source_kind": self.source_kind,
            "question": self.question,
            "answer": self.answer,
            "body_text": self.body_text,
            "keywords": list(self.keywords),
            "business_domain": self.business_domain,
            "document_type": self.document_type,
            "source_type": self.source_type,
            "source_label": self.source_label,
            "source_locator": self.source_locator,
            "access_scope": self.access_scope,
            "lifecycle_status": self.lifecycle_status,
            "valid_from": self.valid_from,
            "valid_until": self.valid_until or "",
            "version": self.version,
            "created_at": self.created_at,
            "tenant_id": self.tenant_id,
            "source_record_id": self.source_record_id or "",
            "unit_version": self.unit_version,
            "fresh_until": self.fresh_until or "",
            "stale_after": self.stale_after or "",
            "import_batch_id": self.import_batch_id or "",
            "published_at": self.published_at or "",
        }


def map_faq_item_to_knowledge_unit(
    item: dict[str, Any], *, default_domain: str = "hr"
) -> KnowledgeUnit:
    return KnowledgeUnit(
        unit_id=item.get("id", ""),
        source_kind="faq",
        question=item.get("question", ""),
        answer=item.get("answer", ""),
        body_text=item.get("answer", ""),
        keywords=tuple(item.get("keywords", [])),
        business_domain=item.get("business_domain", default_domain),
        document_type=item.get("document_type", "faq"),
        source_type=item.get("source_type", "manual_faq"),
        source_label=item.get("source_label", "FAQ"),
        source_locator=item.get("source_locator", item.get("id", "")),
        access_scope=item.get("access_scope", "internal"),
        lifecycle_status=item.get("lifecycle_status", "active"),
        valid_from=item.get("valid_from", ""),
        valid_until=item.get("valid_until") or None,
        version=item.get("version", "v1"),
        created_at=item.get("created_at", ""),
        tenant_id=item.get("tenant_id", "default"),
        source_record_id=item.get("source_record_id"),
        unit_version=int(item.get("unit_version") or 1),
        fresh_until=item.get("fresh_until"),
        stale_after=item.get("stale_after"),
        import_batch_id=item.get("import_batch_id"),
        published_at=item.get("published_at"),
    )


def map_chunk_to_knowledge_unit(chunk: dict[str, Any]) -> KnowledgeUnit:
    return KnowledgeUnit(
        unit_id=chunk.get("chunk_id", ""),
        source_kind="document_chunk",
        question="",
        answer=chunk.get("text", ""),
        body_text=chunk.get("text", ""),
        keywords=tuple(chunk.get("keywords", [])),
        business_domain="",
        document_type="document",
        source_type="document_chunk",
        source_label=chunk.get("source_label", chunk.get("filename", "Document")),
        source_locator=chunk.get("source_locator", chunk.get("chunk_id", "")),
        access_scope="internal",
        lifecycle_status=chunk.get("lifecycle_status", "active"),
        valid_from="",
        valid_until=None,
        version="v1",
        created_at=chunk.get("created_at", ""),
        tenant_id=chunk.get("tenant_id", "default"),
        source_record_id=chunk.get("source_record_id"),
        unit_version=int(chunk.get("unit_version") or 1),
        fresh_until=chunk.get("fresh_until"),
        stale_after=chunk.get("stale_after"),
        import_batch_id=chunk.get("import_batch_id"),
        published_at=chunk.get("published_at"),
    )


class KnowledgeUnitRepository:
    def __init__(
        self,
        *,
        faq_repo: Any | None = None,
        chunk_repo: Any | None = None,
    ) -> None:
        self._faq_repo = faq_repo
        self._chunk_repo = chunk_repo
        storage_root = Path(__file__).resolve().parents[1]
        self._seed_dir = storage_root / "seed"
        self._upload_dir = storage_root / "uploads"

    def list_all(self) -> list[KnowledgeUnit]:
        units: list[KnowledgeUnit] = []
        known_faq_ids: set[str] = set()

        if self._faq_repo is not None:
            for item in self._faq_repo.list_all():
                unit = map_faq_item_to_knowledge_unit(item)
                units.append(unit)
                if unit.unit_id:
                    known_faq_ids.add(unit.unit_id)

        for item in self._list_markdown_faq_items():
            unit = map_faq_item_to_knowledge_unit(item)
            if unit.unit_id and unit.unit_id not in known_faq_ids:
                units.append(unit)
                known_faq_ids.add(unit.unit_id)

        if self._chunk_repo is not None:
            for chunk in self._chunk_repo.list_all():
                units.append(map_chunk_to_knowledge_unit(chunk))

        return units

    def list_by_source_record(
        self, source_record_id: str, *, active_only: bool = True
    ) -> list[KnowledgeUnit]:
        units = [
            unit
            for unit in self.list_all()
            if unit.source_record_id == source_record_id
        ]
        if active_only:
            return [unit for unit in units if unit.lifecycle_status == "active"]
        return units

    def update_status_by_source_record(
        self, source_record_id: str, lifecycle_status: str
    ) -> list[str]:
        target_status = _normalize_knowledge_unit_status(lifecycle_status)
        updated_ids: list[str] = []
        updated_ids.extend(
            _update_repo_status_by_source_record(
                self._faq_repo,
                source_record_id,
                target_status,
            )
        )
        updated_ids.extend(
            _update_repo_status_by_source_record(
                self._chunk_repo,
                source_record_id,
                target_status,
            )
        )
        return updated_ids

    def list_faq_units(self) -> list[KnowledgeUnit]:
        units: list[KnowledgeUnit] = []
        known_faq_ids: set[str] = set()

        if self._faq_repo is not None:
            for item in self._faq_repo.list_all():
                unit = map_faq_item_to_knowledge_unit(item)
                units.append(unit)
                if unit.unit_id:
                    known_faq_ids.add(unit.unit_id)

        for item in self._list_markdown_faq_items():
            unit = map_faq_item_to_knowledge_unit(item)
            if unit.unit_id and unit.unit_id not in known_faq_ids:
                units.append(unit)
                known_faq_ids.add(unit.unit_id)

        return units

    def list_chunk_units(self) -> list[KnowledgeUnit]:
        if self._chunk_repo is None:
            return []
        return [
            map_chunk_to_knowledge_unit(chunk) for chunk in self._chunk_repo.list_all()
        ]

    def _list_markdown_faq_items(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []

        for base_dir in (self._seed_dir, self._upload_dir):
            if not base_dir.exists():
                continue
            for path in sorted(base_dir.glob("*_faq_seed_*.md")):
                items.extend(_parse_seed_markdown_faq_items(path))

        return items


def _parse_seed_markdown_faq_items(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    match = re.search(r"```json\s*(\[[\s\S]*?\])\s*```", text)
    if match is None:
        return []

    payload = json.loads(match.group(1))
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def _normalize_knowledge_unit_status(status: str) -> str:
    # KnowledgeUnit.lifecycle_status does not have a "deleted" value; deleted
    # source records are made runtime-invisible by revoking their published units.
    if status == "deleted":
        return "revoked"
    return status


def _update_repo_status_by_source_record(
    repo: Any | None, source_record_id: str, lifecycle_status: str
) -> list[str]:
    if repo is None or not hasattr(repo, "update_status_by_source_record"):
        return []

    updated = repo.update_status_by_source_record(source_record_id, lifecycle_status)
    return [str(unit_id) for unit_id in updated]
