from __future__ import annotations

import re
from typing import Protocol

import httpx


class ExtractionProvider(Protocol):
    name: str

    def complete(self, messages: list[dict[str, str]]) -> str: ...


class OpenAICompatibleExtractionProvider:
    def __init__(
        self,
        *,
        api_base: str,
        api_model: str,
        api_key: str,
        timeout_seconds: float,
        provider_name: str = "openai_compatible",
    ) -> None:
        self.name = provider_name
        self._api_base = api_base.rstrip("/")
        self._api_model = api_model
        self._api_key = api_key
        self._timeout = timeout_seconds

    def complete(self, messages: list[dict[str, str]]) -> str:
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
            raise RuntimeError(f"{self.name} timeout: {exc}") from exc
        except httpx.HTTPError as exc:
            raise RuntimeError(f"{self.name} error: {exc}") from exc

        if response.status_code != 200:
            raise RuntimeError(f"{self.name} status={response.status_code}")

        envelope = response.json()
        choices = envelope.get("choices", [])
        if not choices:
            return ""

        content = choices[0].get("message", {}).get("content", "")
        content = re.sub(
            r"<think\b[^>]*>.*?</think\s*>",
            "",
            content,
            flags=re.DOTALL | re.IGNORECASE,
        ).strip()

        if content.startswith("```"):
            lines = content.split("\n")
            lines = [line for line in lines if not line.startswith("```")]
            content = "\n".join(lines).strip()

        return content
