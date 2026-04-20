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
        lifecycle_status="active",
        valid_from="",
        valid_until=None,
        version="v1",
        created_at=chunk.get("created_at", ""),
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
