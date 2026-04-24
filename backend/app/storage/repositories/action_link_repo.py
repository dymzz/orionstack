from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.storage.models.action_link import ActionLink

_STORAGE_DIR = Path(__file__).resolve().parents[1] / "action_links"


class ActionLinkRepo:
    def __init__(self, storage_dir: Path | None = None) -> None:
        self._dir = storage_dir or _STORAGE_DIR
        self._dir.mkdir(parents=True, exist_ok=True)
        self._file = self._dir / "action_links.jsonl"

    def create(self, link: ActionLink) -> None:
        self._append(link)

    def get(self, action_link_id: str) -> ActionLink | None:
        for link in self._iter_all():
            if link.action_link_id == action_link_id:
                return link
        return None

    def list_active(self) -> list[ActionLink]:
        return [l for l in self._iter_all() if l.status == "active"]

    def list_by_resource_type(self, resource_type: str) -> list[ActionLink]:
        return [l for l in self._iter_all() if l.resource_type == resource_type and l.status == "active"]

    def list_by_source_record(self, source_record_id: str) -> list[ActionLink]:
        return [l for l in self._iter_all() if l.source_record_id == source_record_id and l.status == "active"]

    def upsert(self, link: ActionLink) -> None:
        existing = self._find_by_system_and_resource(link.system_type, link.resource_type)
        if existing is not None:
            self._remove(existing.action_link_id)
        self._append(link)

    def update_status(self, action_link_id: str, status: str) -> None:
        links = list(self._iter_all())
        self._file.write_text("", encoding="utf-8")
        for l in links:
            if l.action_link_id == action_link_id:
                from dataclasses import replace
                l = replace(l, status=status)
            self._append(l)

    def _find_by_system_and_resource(self, system_type: str, resource_type: str) -> ActionLink | None:
        for l in self._iter_all():
            if l.system_type == system_type and l.resource_type == resource_type:
                return l
        return None

    def _remove(self, action_link_id: str) -> None:
        links = [l for l in self._iter_all() if l.action_link_id != action_link_id]
        self._file.write_text("", encoding="utf-8")
        for l in links:
            self._append(l)

    def _append(self, link: ActionLink) -> None:
        with open(self._file, "a", encoding="utf-8") as f:
            f.write(json.dumps(link.to_dict(), ensure_ascii=False) + "\n")

    def _iter_all(self) -> list[ActionLink]:
        if not self._file.exists():
            return []
        lines = self._file.read_text(encoding="utf-8").strip().split("\n")
        results: list[ActionLink] = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            results.append(self._parse(json.loads(line)))
        return results

    @staticmethod
    def _parse(d: dict[str, Any]) -> ActionLink:
        return ActionLink(
            action_link_id=d["action_link_id"],
            tenant_id=d.get("tenant_id", "default"),
            source_record_id=d.get("source_record_id", ""),
            label=d["label"],
            system_type=d["system_type"],
            url=d["url"],
            resource_type=d["resource_type"],
            access_scope=d.get("access_scope", "internal"),
            status=d.get("status", "active"),
            published_at=d.get("published_at", ""),
            fresh_until=d.get("fresh_until"),
        )
