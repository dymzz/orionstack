"""Embedding contract and explicit provider selection; model spaces never fall back implicitly."""

import hashlib
import json
import math
from typing import Literal, Protocol
from urllib.parse import quote

import httpx
from pydantic import Field, ValidationError

from app.config.core_settings import CoreSettings
from app.providers.http import ProviderError, post_json
from app.knowledge.contracts import CoreContract, content_hash


class EmbeddingSignature(CoreContract):
    provider: Literal["cloudflare_workers_ai", "onnxruntime"] = "cloudflare_workers_ai"
    model: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    dimensions: int = Field(gt=0, strict=True)
    normalization: Literal["l2"] = "l2"
    metric: Literal["cosine"] = "cosine"
    preprocessing: Literal["exact_text_v1", "qwen3_last_token_query_instruction_v1"] = "exact_text_v1"
    truncation: Literal["reject"] = "reject"

    @property
    def fingerprint(self) -> str:
        return content_hash(json.dumps(self.model_dump(), sort_keys=True, separators=(",", ":")))


class EmbeddingBatch(CoreContract):
    signature: EmbeddingSignature
    vectors: tuple[tuple[float, ...], ...]
    input_hashes: tuple[str, ...]


class EmbeddingClient(Protocol):
    @property
    def signature(self) -> EmbeddingSignature: ...

    def embed(self, texts: tuple[str, ...]) -> EmbeddingBatch: ...

    def embed_query(self, text: str) -> EmbeddingBatch: ...


def create_embedding_client(settings: CoreSettings | None = None) -> EmbeddingClient:
    settings = settings or CoreSettings()
    if settings.embedding_provider == "cloudflare_workers_ai":
        return WorkersAIEmbeddingClient(settings)
    from app.knowledge.onnx_embedding import OnnxEmbeddingClient
    return OnnxEmbeddingClient(settings)


def normalized_vector(values: tuple[float, ...] | list[float], dimensions: int) -> tuple[float, ...]:
    if len(values) != dimensions or any(isinstance(value, bool) or not isinstance(value, (int, float))
                                       or not math.isfinite(value) for value in values):
        raise ValueError("Embedding vector dimensions or numeric values are invalid")
    norm = math.hypot(*values)
    if not math.isfinite(norm) or norm <= 0:
        raise ValueError("Embedding vector must be finite and nonzero")
    return tuple(value / norm for value in values)


class WorkersAIEmbeddingClient:
    def __init__(self, settings: CoreSettings | None = None, client: httpx.Client | None = None) -> None:
        self.settings = settings or CoreSettings()
        self.client = client

    @property
    def signature(self) -> EmbeddingSignature:
        return EmbeddingSignature(model=self.settings.embedding_model,
                                  revision=self.settings.embedding_revision,
                                  dimensions=self.settings.embedding_dimensions)

    def embed(self, texts: tuple[str, ...]) -> EmbeddingBatch:
        if not texts or len(texts) > 32 or any(not isinstance(text, str) or not text.strip() for text in texts):
            raise ValueError("Embedding requires between 1 and 32 nonblank texts")
        account_id, token = self.settings.require_cloudflare()
        url = ("https://api.cloudflare.com/client/v4/accounts/" + quote(account_id, safe="")
               + "/ai/run/" + quote(self.settings.embedding_model, safe="@/"))
        # Reject oversized model inputs instead of silently embedding a truncated prefix.
        raw = post_json("workers_ai", url, token, {"text": list(texts), "truncate_inputs": False},
                        self.settings.provider_timeout_seconds, self.client)
        try:
            if raw.get("success") is not True or raw.get("errors") not in ([], None):
                raise ValueError
            result = raw["result"]
            if not isinstance(result, dict) or result.get("shape") != [len(texts), self.signature.dimensions]:
                raise ValueError
            data = result["data"]
            if not isinstance(data, list) or len(data) != len(texts):
                raise ValueError
            vectors = tuple(normalized_vector(vector, self.signature.dimensions) for vector in data)
            return EmbeddingBatch(signature=self.signature, vectors=vectors,
                                  input_hashes=tuple(content_hash(text) for text in texts))
        except (KeyError, TypeError, ValueError, ValidationError):
            raise ProviderError("workers_ai", "invalid_embedding_response") from None

    def embed_query(self, text: str) -> EmbeddingBatch:
        return self.embed((text,))


def vector_fingerprint(vector: tuple[float, ...]) -> str:
    # Float.hex preserves exactly the query vector submitted to pgvector.
    return hashlib.sha256("|".join(value.hex() for value in vector).encode("ascii")).hexdigest()
