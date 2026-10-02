from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.storage.models.extraction_candidate import ExtractionCandidate
from app.storage.repositories.base_repo import JsonlLock

_STORAGE_DIR = Path(__file__).resolve().parents[1] / "extraction_candidates"


class ExtractionCandidateRepo:
    def __init__(self, storage_dir: Path | None = None) -> None:
        self._dir = storage_dir or _STORAGE_DIR
        self._dir.mkdir(parents=True, exist_ok=True)
        self._file = self._dir / "candidates.jsonl"
        self._lock = JsonlLock(self._file)

    def create(self, candidate: ExtractionCandidate) -> None:
        with self._lock:
            self._append(candidate)

    def get(self, candidate_id: str) -> ExtractionCandidate | None:
        for c in self._iter_all():
            if c.candidate_id == candidate_id:
                return c
        return None

    def list_by_source_record(self, source_record_id: str) -> list[ExtractionCandidate]:
        return [c for c in self._iter_all() if c.source_record_id == source_record_id]

    def list_by_review_status(self, review_status: str) -> list[ExtractionCandidate]:
        return [c for c in self._iter_all() if c.review_status == review_status]

    def update_review_status(
        self,
        candidate_id: str,
        review_status: str,
        reviewed_by: str | None = None,
    ) -> ExtractionCandidate | None:
        with self._lock:
            candidates = list(self._iter_all())
            updated: ExtractionCandidate | None = None
            self._file.write_text("", encoding="utf-8")
            for c in candidates:
                if c.candidate_id == candidate_id:
                    from dataclasses import replace
                    from datetime import datetime, timezone
                    c = replace(
                        c,
                        review_status=review_status,
                        reviewed_by=reviewed_by,
                        reviewed_at=datetime.now(timezone.utc).isoformat(),
                    )
                    updated = c
                self._append(c)
        return updated

    def _append(self, candidate: ExtractionCandidate) -> None:
        with open(self._file, "a", encoding="utf-8") as f:
            f.write(json.dumps(candidate.to_dict(), ensure_ascii=False) + "\n")

    def _iter_all(self) -> list[ExtractionCandidate]:
        if not self._file.exists():
            return []
        lines = self._file.read_text(encoding="utf-8").strip().split("\n")
        results: list[ExtractionCandidate] = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            results.append(self._parse(json.loads(line)))
        return results

    @staticmethod
    def _parse(d: dict[str, Any]) -> ExtractionCandidate:
        return ExtractionCandidate(
            candidate_id=d["candidate_id"],
            tenant_id=d.get("tenant_id", "default"),
            source_record_id=d["source_record_id"],
            candidate_type=d["candidate_type"],
            payload_json=d["payload_json"],
            extractor_model=d["extractor_model"],
            prompt_version=d["prompt_version"],
            source_span=d["source_span"],
            source_span_hash=d["source_span_hash"],
            review_status=d.get("review_status", "pending"),
            created_at=d["created_at"],
            reviewed_by=d.get("reviewed_by"),
            reviewed_at=d.get("reviewed_at"),
        )
