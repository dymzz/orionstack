from __future__ import annotations

import os
from collections.abc import Callable
from typing import TYPE_CHECKING

from app.extract.providers.openai_compatible_provider import (
    ExtractionProvider,
    OpenAICompatibleExtractionProvider,
)

if TYPE_CHECKING:
    from app.config.settings import Settings

ExtractionProviderFactory = Callable[["Settings"], ExtractionProvider]


def _resolve_provider_api_key(
    env_names: list[str], *, allow_dummy_default: bool = False
) -> str:
    for env_name in env_names:
        value = os.environ.get(env_name, "").strip()
        if value:
            return value
    if allow_dummy_default:
        return "dummy-not-required"
    return ""


def _build_openai_compatible_provider(settings: "Settings") -> ExtractionProvider:
    return OpenAICompatibleExtractionProvider(
        api_base=settings.extraction_api_base,
        api_model=settings.extraction_api_model,
        api_key=_resolve_provider_api_key(
            [
                "ORIONSTACK_EXTRACTION_API_KEY",
                "ORIONSTACK_QWEN_API_KEY",
                "DASHSCOPE_API_KEY",
            ]
        ),
        timeout_seconds=settings.planner_timeout_seconds,
        provider_name="openai_compatible",
    )


def _build_qwen_api_alias_provider(settings: "Settings") -> ExtractionProvider:
    # Historical alias kept for compatibility with older env/config values.
    return OpenAICompatibleExtractionProvider(
        api_base=settings.extraction_api_base,
        api_model=settings.extraction_api_model,
        api_key=_resolve_provider_api_key(
            [
                "ORIONSTACK_EXTRACTION_API_KEY",
                "ORIONSTACK_QWEN_API_KEY",
                "DASHSCOPE_API_KEY",
            ]
        ),
        timeout_seconds=settings.planner_timeout_seconds,
        provider_name="qwen_api",
    )


def _build_llama_cpp_provider(settings: "Settings") -> ExtractionProvider:
    return OpenAICompatibleExtractionProvider(
        api_base=settings.local_llm_base_url,
        api_model=settings.local_llm_model,
        api_key=_resolve_provider_api_key(
            [
                "ORIONSTACK_EXTRACTION_API_KEY",
                "ORIONSTACK_QWEN_API_KEY",
                "DASHSCOPE_API_KEY",
            ],
            allow_dummy_default=True,
        ),
        timeout_seconds=settings.planner_timeout_seconds,
        provider_name="llama_cpp",
    )


_EXTRACTION_PROVIDER_FACTORIES: dict[str, ExtractionProviderFactory] = {
    "openai_compatible": _build_openai_compatible_provider,
    "qwen_api": _build_qwen_api_alias_provider,
    "llama_cpp": _build_llama_cpp_provider,
}


def build_extraction_provider(
    name: str, settings: "Settings"
) -> ExtractionProvider:
    provider_name = name.strip().lower()
    factory = _EXTRACTION_PROVIDER_FACTORIES.get(provider_name)
    if factory is None:
        raise ValueError(f"unknown extraction provider: {provider_name!r}")
    return factory(settings)


def register_extraction_provider(
    name: str, factory: ExtractionProviderFactory
) -> None:
    _EXTRACTION_PROVIDER_FACTORIES[name.strip().lower()] = factory


# Compatibility alias for older imports/tests. Prefer `build_extraction_provider`.
create_extraction_provider = build_extraction_provider


__all__ = [
    "ExtractionProvider",
    "OpenAICompatibleExtractionProvider",
    "build_extraction_provider",
    "create_extraction_provider",
    "register_extraction_provider",
]
