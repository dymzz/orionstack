from __future__ import annotations

from collections.abc import Iterator
import json
import os
from typing import Any, Protocol

import httpx


class ModelRuntime(Protocol):
    def generate(
        self,
        *,
        model: str,
        prompt: str,
        response_format: dict[str, Any] | None = None,
        timeout: float = 30.0,
    ) -> str: ...

    def stream_generate(
        self,
        *,
        model: str,
        prompt: str,
        timeout: float = 45.0,
    ) -> Iterator[str]: ...

    def embed_texts(
        self,
        *,
        model: str,
        texts: list[str],
        timeout: float = 30.0,
    ) -> list[list[float]]: ...


class OllamaModelRuntime:
    def __init__(self, *, base_url: str | None = None) -> None:
        self.base_url = base_url or os.getenv("ORIONSTACK_OLLAMA_BASE_URL", "http://127.0.0.1:11434")

    def generate(
        self,
        *,
        model: str,
        prompt: str,
        response_format: dict[str, Any] | None = None,
        timeout: float = 30.0,
    ) -> str:
        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": False,
        }
        if response_format is not None:
            payload["format"] = response_format

        with httpx.Client(timeout=timeout) as client:
            response = client.post(f"{self.base_url}/api/generate", json=payload)
            response.raise_for_status()
            data = response.json()
        return str(data.get("response", "")).strip()

    def stream_generate(
        self,
        *,
        model: str,
        prompt: str,
        timeout: float = 45.0,
    ) -> Iterator[str]:
        with httpx.stream(
            "POST",
            f"{self.base_url}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": True,
            },
            timeout=timeout,
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line:
                    continue
                packet = json.loads(line)
                token = str(packet.get("response", ""))
                if token:
                    yield token

    def embed_texts(
        self,
        *,
        model: str,
        texts: list[str],
        timeout: float = 30.0,
    ) -> list[list[float]]:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(
                f"{self.base_url}/api/embed",
                json={"model": model, "input": texts},
            )
            response.raise_for_status()
            data = response.json()

        vectors = data.get("embeddings")
        if not isinstance(vectors, list) or not vectors:
            raise ValueError("Ollama did not return embeddings")
        return [list(vector) for vector in vectors]


class ModelRuntimeRegistry:
    def __init__(self) -> None:
        self._runtimes: dict[str, ModelRuntime] = {
            "ollama": OllamaModelRuntime(),
        }

    def is_supported(self, provider: str | None) -> bool:
        provider_name = (provider or "ollama").strip().lower() or "ollama"
        return provider_name in self._runtimes

    def resolve(self, provider: str | None) -> ModelRuntime:
        provider_name = (provider or "ollama").strip().lower() or "ollama"
        runtime = self._runtimes.get(provider_name)
        if runtime is None:
            raise ValueError(f"Unsupported model provider: {provider_name}")
        return runtime


class ModelGateway:
    def __init__(self) -> None:
        self.registry = ModelRuntimeRegistry()

    def generate(
        self,
        *,
        provider: str | None,
        model: str,
        prompt: str,
        response_format: dict[str, Any] | None = None,
        timeout: float = 30.0,
    ) -> str:
        runtime = self.registry.resolve(provider)
        return runtime.generate(
            model=model,
            prompt=prompt,
            response_format=response_format,
            timeout=timeout,
        )

    def stream_generate(
        self,
        *,
        provider: str | None,
        model: str,
        prompt: str,
        timeout: float = 45.0,
    ) -> Iterator[str]:
        runtime = self.registry.resolve(provider)
        return runtime.stream_generate(
            model=model,
            prompt=prompt,
            timeout=timeout,
        )

    def embed_texts(
        self,
        *,
        provider: str | None,
        model: str,
        texts: list[str],
        timeout: float = 30.0,
    ) -> list[list[float]]:
        runtime = self.registry.resolve(provider)
        return runtime.embed_texts(
            model=model,
            texts=texts,
            timeout=timeout,
        )
