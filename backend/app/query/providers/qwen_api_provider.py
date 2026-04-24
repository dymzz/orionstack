"""Legacy compatibility wrapper for the OpenAI-compatible planner provider."""

from __future__ import annotations

from app.query.providers.openai_compatible_provider import (
    OpenAICompatiblePlannerProvider,
    _SYSTEM_PROMPT,
)


class QwenApiProvider(OpenAICompatiblePlannerProvider):
    """Compatibility alias around the generic OpenAI-compatible provider."""

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("provider_name", "qwen_api")
        super().__init__(**kwargs)
