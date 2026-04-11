from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
import os
from typing import Iterable

import httpx


@dataclass
class EmbeddingBatch:
    model: str
    dimension: int
    vectors: list[list[float]]
    provider: str


class EmbeddingService:
    def __init__(self) -> None:
        self.provider = os.getenv("ORIONSTACK_EMBEDDING_PROVIDER", "ollama")
        self.ollama_base_url = os.getenv("ORIONSTACK_OLLAMA_BASE_URL", "http://127.0.0.1:11434")
        self.ollama_model = os.getenv("ORIONSTACK_EMBEDDING_MODEL", "bge-m3")
        self.batch_size = max(1, int(os.getenv("ORIONSTACK_EMBEDDING_BATCH_SIZE", "8")))
        self.fallback_model = "local-hash-v1"
        self.fallback_dimension = 256

    def embed_texts(self, texts: Iterable[str], provider_override: str | None = None) -> EmbeddingBatch:
        items = [str(text) for text in texts]
        if not items:
            return EmbeddingBatch(
                model=self.fallback_model,
                dimension=self.fallback_dimension,
                vectors=[],
                provider="fallback",
            )

        provider = (provider_override or self.provider).lower()

        if provider == "ollama":
            try:
                return self._embed_with_ollama(items)
            except Exception:
                if provider_override == "ollama":
                    raise
                pass

        return self._embed_with_hash(items)

    def embed_texts_in_batches(self, texts: Iterable[str], batch_size: int | None = None) -> list[EmbeddingBatch]:
        items = [str(text) for text in texts]
        if not items:
            return []

        effective_batch_size = max(1, batch_size or self.batch_size)
        committed_provider: str | None = None
        batches: list[EmbeddingBatch] = []

        for start in range(0, len(items), effective_batch_size):
            current_items = items[start : start + effective_batch_size]
            batch = self.embed_texts(current_items, provider_override=committed_provider)
            if committed_provider is None:
                committed_provider = "ollama" if batch.provider == "ollama" else "fallback"
            batches.append(batch)

        return batches

    def _embed_with_ollama(self, texts: list[str]) -> EmbeddingBatch:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                f"{self.ollama_base_url}/api/embed",
                json={"model": self.ollama_model, "input": texts},
            )
            response.raise_for_status()
            data = response.json()

        vectors = data.get("embeddings")
        if not isinstance(vectors, list) or not vectors:
            raise ValueError("Ollama did not return embeddings")

        normalized_vectors = [self._normalize_vector(vector) for vector in vectors]
        dimension = len(normalized_vectors[0])
        return EmbeddingBatch(
            model=self.ollama_model,
            dimension=dimension,
            vectors=normalized_vectors,
            provider="ollama",
        )

    def _embed_with_hash(self, texts: list[str]) -> EmbeddingBatch:
        vectors = [self._hash_embed(text) for text in texts]
        return EmbeddingBatch(
            model=self.fallback_model,
            dimension=self.fallback_dimension,
            vectors=vectors,
            provider="fallback",
        )

    def _hash_embed(self, text: str) -> list[float]:
        vector = [0.0] * self.fallback_dimension
        normalized = " ".join(text.lower().split())
        if not normalized:
            return vector

        features: list[str] = []
        features.extend(normalized.split())
        features.extend(list(normalized))

        for feature in features:
            digest = hashlib.sha256(feature.encode("utf-8")).digest()
            slot = int.from_bytes(digest[:4], "big") % self.fallback_dimension
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            weight = 1.0 + (digest[5] / 255.0)
            vector[slot] += sign * weight

        return self._normalize_vector(vector)

    def _normalize_vector(self, vector: list[float]) -> list[float]:
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [value / norm for value in vector]
