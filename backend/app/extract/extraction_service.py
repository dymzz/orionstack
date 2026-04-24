from __future__ import annotations

import json
import re
from typing import Any

import httpx

from app.config.settings import settings
from app.extract.prompt_templates import build_extraction_messages, parse_extraction_response
from app.extract.llm_extractor import extract_candidates
from app.storage.models.extraction_candidate import ExtractionCandidate
from app.storage.models.source_record import SourceRecord
from app.storage.repositories.extraction_candidate_repo import ExtractionCandidateRepo


class ExtractionService:
    def __init__(
        self,
        candidate_repo: ExtractionCandidateRepo | None = None,
        api_base: str | None = None,
        api_model: str | None = None,
        api_key: str | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        self._repo = candidate_repo or ExtractionCandidateRepo()
        self._api_base = (api_base or settings.qwen_api_base).rstrip("/")
        self._api_model = api_model or settings.qwen_api_model
        self._api_key = api_key or self._resolve_api_key()
        self._timeout = timeout_seconds or settings.planner_timeout_seconds

    @staticmethod
    def _resolve_api_key() -> str:
        import os
        return os.getenv("ORIONSTACK_QWEN_API_KEY") or os.getenv("DASHSCOPE_API_KEY", "")

    def extract_from_record(
        self,
        source_record: SourceRecord,
        candidate_types: list[str] | None = None,
    ) -> list[ExtractionCandidate]:
        messages = build_extraction_messages(source_record.raw_content, candidate_types)
        content = self._call_api(messages)
        raw_candidates = parse_extraction_response(content)

        payloads: list[dict[str, Any]] = []
        for rc in raw_candidates:
            rc["_source_span"] = source_record.title or source_record.source_locator
            payloads.append(rc)

        candidates = extract_candidates(
            source_record=source_record,
            candidate_type="mixed",
            payloads=payloads,
            extractor_model=self._api_model,
            prompt_version="v1",
            tenant_id=source_record.tenant_id,
        )

        for c in candidates:
            self._repo.create(c)

        return candidates

    def _call_api(self, messages: list[dict[str, str]]) -> str:
        url = f"{self._api_base}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._api_model,
            "messages": messages,
            "temperature": 0.0,
            "max_tokens": 2048,
            "response_format": {"type": "json_object"},
        }

        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.post(url, headers=headers, json=payload)
        except httpx.TimeoutException as exc:
            raise RuntimeError(f"extraction api timeout: {exc}") from exc
        except httpx.HTTPError as exc:
            raise RuntimeError(f"extraction api error: {exc}") from exc

        if response.status_code != 200:
            raise RuntimeError(f"extraction api status={response.status_code}")

        envelope = response.json()
        choices = envelope.get("choices", [])
        if not choices:
            return ""

        content = choices[0].get("message", {}).get("content", "")
        content = re.sub(r"<think\b[^>]*>.*?</think\s*>", "", content, flags=re.DOTALL | re.IGNORECASE).strip()

        if content.startswith("```"):
            lines = content.split("\n")
            lines = [l for l in lines if not l.startswith("```")]
            content = "\n".join(lines).strip()

        return content
