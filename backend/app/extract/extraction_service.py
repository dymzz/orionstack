from __future__ import annotations

from typing import Any

from app.config.settings import settings
from app.extract.prompt_templates import build_extraction_messages, parse_extraction_response
from app.extract.providers import ExtractionProvider, build_extraction_provider
from app.extract.llm_extractor import extract_candidates
from app.storage.models.extraction_candidate import ExtractionCandidate
from app.storage.models.source_record import SourceRecord
from app.storage.repositories.extraction_candidate_repo import ExtractionCandidateRepo


class ExtractionService:
    def __init__(
        self,
        candidate_repo: ExtractionCandidateRepo | None = None,
        provider: ExtractionProvider | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        self._repo = candidate_repo or ExtractionCandidateRepo()
        self._timeout = timeout_seconds or settings.planner_timeout_seconds
        self._provider = provider or build_extraction_provider(
            settings.extraction_provider, settings
        )

    def extract_from_record(
        self,
        source_record: SourceRecord,
        candidate_types: list[str] | None = None,
    ) -> list[ExtractionCandidate]:
        messages = build_extraction_messages(source_record.raw_content, candidate_types)
        content = self._complete_messages(messages)
        raw_candidates = parse_extraction_response(content)

        payloads: list[dict[str, Any]] = []
        for rc in raw_candidates:
            rc["_source_span"] = source_record.title or source_record.source_locator
            payloads.append(rc)

        candidates = extract_candidates(
            source_record=source_record,
            candidate_type="mixed",
            payloads=payloads,
            extractor_model=getattr(self._provider, "_api_model", self._provider.name),
            prompt_version="v1",
            tenant_id=source_record.tenant_id,
        )

        for c in candidates:
            self._repo.create(c)

        return candidates

    def _complete_messages(self, messages: list[dict[str, str]]) -> str:
        # Transport/protocol details live in the provider; the service only
        # owns prompt construction and persistence.
        return self._provider.complete(messages)
