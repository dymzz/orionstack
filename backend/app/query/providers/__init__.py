"""Planner provider implementations.

See docs/2_7_planner_upgrade_plan.md §1.3 for the provider roster and
docs/2_8_planner_llm_integration.md for the integration plan.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import TYPE_CHECKING

from app.query.providers.errors import (
    PlannerHttpError,
    PlannerParseError,
    PlannerProviderError,
    PlannerSchemaError,
    PlannerTimeoutError,
)
from app.query.providers.openai_compatible_provider import (
    OpenAICompatiblePlannerProvider,
)
from app.query.providers.qwen_api_provider import QwenApiProvider

if TYPE_CHECKING:
    from app.config.settings import Settings
    from app.query.query_planner import PlannerProvider

PlannerProviderFactory = Callable[["Settings"], "PlannerProvider"]


def _resolve_provider_api_key(
    env_names: list[str], *, allow_dummy_default: bool = False
) -> str:
    for env_name in env_names:
        value = os.environ.get(env_name, "").strip()
        if value:
            return value
    if allow_dummy_default:
        return "dummy-not-required"
    searched = " / ".join(env_names)
    raise ValueError(f"{searched} environment variable is required")


def _build_qwen_api_alias_provider(settings: "Settings") -> "PlannerProvider":
    # Keep the historical provider id as a compatibility alias. New code
    # should prefer `openai_compatible` unless it intentionally targets the
    # old qwen_api entry point.
    return QwenApiProvider(
        api_base=settings.planner_api_base,
        api_model=settings.planner_api_model,
        api_key=_resolve_provider_api_key(
            [
                "ORIONSTACK_PLANNER_API_KEY",
                "ORIONSTACK_LLM_API_KEY",
                "DASHSCOPE_API_KEY",
                "QWEN_API_KEY",
            ]
        ),
        timeout_seconds=settings.planner_timeout_seconds,
    )


def _build_openai_compatible_provider(settings: "Settings") -> "PlannerProvider":
    return OpenAICompatiblePlannerProvider(
        api_base=settings.planner_api_base,
        api_model=settings.planner_api_model,
        api_key=_resolve_provider_api_key(
            [
                "ORIONSTACK_PLANNER_API_KEY",
                "ORIONSTACK_LLM_API_KEY",
                "DASHSCOPE_API_KEY",
                "QWEN_API_KEY",
            ]
        ),
        timeout_seconds=settings.planner_timeout_seconds,
        provider_name="openai_compatible",
    )


def _build_llama_cpp_provider(settings: "Settings") -> "PlannerProvider":
    return OpenAICompatiblePlannerProvider(
        api_base=settings.local_llm_base_url,
        api_model=settings.local_llm_model,
        api_key=_resolve_provider_api_key(
            [
                "ORIONSTACK_PLANNER_API_KEY",
                "ORIONSTACK_LLM_API_KEY",
                "DASHSCOPE_API_KEY",
                "QWEN_API_KEY",
            ],
            allow_dummy_default=True,
        ),
        timeout_seconds=settings.planner_timeout_seconds,
        provider_name="llama_cpp",
    )


_PLANNER_PROVIDER_FACTORIES: dict[str, PlannerProviderFactory] = {
    "qwen_api": _build_qwen_api_alias_provider,
    "openai_compatible": _build_openai_compatible_provider,
    "llama_cpp": _build_llama_cpp_provider,
}


def build_planner_provider(name: str, settings: "Settings") -> "PlannerProvider":
    provider_name = name.strip().lower()
    factory = _PLANNER_PROVIDER_FACTORIES.get(provider_name)
    if factory is None:
        raise ValueError(f"unknown planner provider: {provider_name!r}")
    return factory(settings)


def register_planner_provider(name: str, factory: PlannerProviderFactory) -> None:
    _PLANNER_PROVIDER_FACTORIES[name.strip().lower()] = factory


# Compatibility alias for older imports/tests. Prefer `build_planner_provider`.
create_planner_provider = build_planner_provider

__all__ = [
    "PlannerProviderError",
    "PlannerTimeoutError",
    "PlannerHttpError",
    "PlannerParseError",
    "PlannerSchemaError",
    "OpenAICompatiblePlannerProvider",
    "QwenApiProvider",
    "build_planner_provider",
    "create_planner_provider",
    "register_planner_provider",
]
