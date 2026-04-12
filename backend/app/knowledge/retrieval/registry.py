from __future__ import annotations

from typing import Any, Protocol

from app.governance.user_context import UserContext
from app.knowledge.retrieval.retrieval_service import RetrievalService


class RetrievalRuntime(Protocol):
    def retrieve(
        self,
        question: str,
        document_ids: list[str] | None = None,
        top_k: int = 5,
        use_rerank: bool = True,
        user_context: UserContext | None = None,
    ) -> list[dict[str, Any]]: ...


class RetrievalRegistry:
    def __init__(self) -> None:
        self._runtimes: dict[str, RetrievalRuntime] = {
            "default": RetrievalService(),
        }

    def is_supported(self, backend: str | None) -> bool:
        backend_name = (backend or "default").strip() or "default"
        return backend_name in self._runtimes

    def resolve(self, backend: str | None) -> RetrievalRuntime:
        backend_name = (backend or "default").strip() or "default"
        runtime = self._runtimes.get(backend_name)
        if runtime is None:
            raise ValueError(f"Unsupported retrieval backend: {backend_name}")
        return runtime
