from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.storage.models.dynamic_query import DynamicQuery

_STORAGE_DIR = Path(__file__).resolve().parents[1] / "dynamic_queries"


class DynamicQueryRepo:
    def __init__(self, storage_dir: Path | None = None) -> None:
        self._dir = storage_dir or _STORAGE_DIR
        self._dir.mkdir(parents=True, exist_ok=True)
        self._file = self._dir / "dynamic_queries.jsonl"

    def create(self, query: DynamicQuery) -> None:
        self._append(query)

    def get(self, dynamic_query_id: str) -> DynamicQuery | None:
        for q in self._iter_all():
            if q.dynamic_query_id == dynamic_query_id:
                return q
        return None

    def get_by_query_key(self, query_key: str) -> DynamicQuery | None:
        for q in self._iter_all():
            if q.query_key == query_key and q.status == "active":
                return q
        return None

    def list_active(self) -> list[DynamicQuery]:
        return [q for q in self._iter_all() if q.status == "active"]

    def list_by_resource_type(self, resource_type: str) -> list[DynamicQuery]:
        return [
            q
            for q in self._iter_all()
            if q.resource_type == resource_type and q.status == "active"
        ]

    def upsert(self, query: DynamicQuery) -> None:
        existing = self._find_by_query_key(query.query_key)
        if existing is not None:
            self._remove(existing.dynamic_query_id)
        self._append(query)

    def update_status(self, dynamic_query_id: str, status: str) -> None:
        queries = list(self._iter_all())
        self._file.write_text("", encoding="utf-8")
        for q in queries:
            if q.dynamic_query_id == dynamic_query_id:
                from dataclasses import replace

                q = replace(q, status=status)
            self._append(q)

    def _find_by_query_key(self, query_key: str) -> DynamicQuery | None:
        for q in self._iter_all():
            if q.query_key == query_key:
                return q
        return None

    def _remove(self, dynamic_query_id: str) -> None:
        queries = [q for q in self._iter_all() if q.dynamic_query_id != dynamic_query_id]
        self._file.write_text("", encoding="utf-8")
        for q in queries:
            self._append(q)

    def _append(self, query: DynamicQuery) -> None:
        with open(self._file, "a", encoding="utf-8") as f:
            f.write(json.dumps(query.to_dict(), ensure_ascii=False) + "\n")

    def _iter_all(self) -> list[DynamicQuery]:
        if not self._file.exists():
            return []
        lines = self._file.read_text(encoding="utf-8").strip().split("\n")
        results: list[DynamicQuery] = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            results.append(self._parse(json.loads(line)))
        return results

    @staticmethod
    def _parse(d: dict[str, Any]) -> DynamicQuery:
        return DynamicQuery(
            dynamic_query_id=d["dynamic_query_id"],
            tenant_id=d.get("tenant_id", "default"),
            query_key=d["query_key"],
            resource_type=d["resource_type"],
            action=d.get("action", "read"),
            scope_type=d.get("scope_type", "self"),
            status=d.get("status", "active"),
            description=d.get("description", ""),
            detect_patterns=tuple(d.get("detect_patterns", [])),
        )
