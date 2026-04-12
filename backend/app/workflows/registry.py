from __future__ import annotations

from collections.abc import Iterator
from typing import Any, Protocol

from app.workflows.knowledge_assistant.workflow import KnowledgeAssistantWorkflow


class WorkflowRuntime(Protocol):
    def run(self, state: dict[str, Any]) -> dict[str, Any]: ...

    def prepare(self, state: dict[str, Any]) -> dict[str, Any]: ...

    def stream_generate_tokens(self, state: dict[str, Any]) -> Iterator[str]: ...

    def finalize(self, state: dict[str, Any], answer: str) -> dict[str, Any]: ...

    def build_fallback_answer(self, state: dict[str, Any]) -> str: ...


class WorkflowRegistry:
    def __init__(self) -> None:
        self._workflows: dict[str, WorkflowRuntime] = {
            "knowledge_assistant": KnowledgeAssistantWorkflow(),
        }

    def is_supported(self, scene: str | None) -> bool:
        scene_name = (scene or "knowledge_assistant").strip() or "knowledge_assistant"
        return scene_name in self._workflows

    def resolve(self, scene: str | None) -> WorkflowRuntime:
        scene_name = (scene or "knowledge_assistant").strip() or "knowledge_assistant"
        workflow = self._workflows.get(scene_name)
        if workflow is None:
            raise ValueError(f"Unsupported workflow scene: {scene_name}")
        return workflow
