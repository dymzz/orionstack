from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class PlannerOutput:
    normalized_query: str
    domain_hint: str | None
    lexical_terms: list[str]
    planner_confidence: float


class PlannerProvider(Protocol):
    """Provider contract for planner implementations.

    See docs/2_7_planner_upgrade_plan.md §3.1 for the rationale and roadmap.
    Provider implementations can target any supported backend so long as they
    satisfy this surface. QueryPlanner stays intentionally thin and dispatches
    by provider name without caring about transport details.
    """

    name: str

    def plan(self, normalized_query: str) -> PlannerOutput: ...


class LocalRuleProvider:
    """Deterministic local planner stub.

    This provider wraps the original inline logic of QueryPlanner.plan() as it
    stood before the 2_7 refactor. It does NOT attempt to satisfy the quality
    contracts listed in docs/2_6_planner_quality_review.md §5 — those
    contracts are tracked in backend/tests/test_planner_contract.py and will
    be closed incrementally by future providers (see 2_7 §2 轮 3).
    """

    name: str = "local"

    def plan(self, normalized_query: str) -> PlannerOutput:
        query = normalized_query.strip()
        if not query:
            return PlannerOutput(
                normalized_query="",
                domain_hint=None,
                lexical_terms=[],
                planner_confidence=0.0,
            )

        lexical_terms = _extract_lexical_terms(query)
        planner_confidence = 0.88 if len(query) >= 2 else 0.05

        return PlannerOutput(
            normalized_query=query,
            domain_hint=None,
            lexical_terms=lexical_terms,
            planner_confidence=planner_confidence,
        )


class QueryPlanner:
    """Planner shell that dispatches to a PlannerProvider with fallback + cache.

    Fallback contract (docs/2_8_planner_llm_integration.md §5):
    - Any PlannerProviderError raised by the primary provider is caught and
      LocalRuleProvider is invoked instead. The fallback_reason (exception
      class name) is recorded on the instance via ``last_fallback_reason``.
    - Fallback is NOT confidence-based. LocalRule confidence is a length
      signal and must not gate LLM upgrade.

    Cache contract (docs/2_8 §5.2):
    - Key is ``normalized_query`` as passed to ``plan()``.
    - Value is the final returned PlannerOutput, regardless of source
      (LLM success, LocalRule fallback, or LocalRule primary).
    - Cache persists for the lifetime of the QueryPlanner instance.
    - Controlled by ``settings.planner_cache_enabled`` (default True).
    """

    def __init__(self, *, provider: str = "local", model: str = "") -> None:
        self._provider_name = provider
        self._model = model
        self._impl: PlannerProvider = self._build_provider(provider, model)
        self._fallback: PlannerProvider = LocalRuleProvider()
        self._cache: dict[str, PlannerOutput] = {}
        self._cache_enabled: bool = self._read_cache_setting()
        self._last_fallback_reason: str | None = None

    def _read_cache_setting(self) -> bool:
        # Lazy import to avoid import cycles at module load time.
        from app.config.settings import settings as _settings

        return _settings.planner_cache_enabled

    def _build_provider(self, name: str, model: str) -> PlannerProvider:
        if name == "local":
            return LocalRuleProvider()
        from app.config.settings import settings as _settings
        from app.query.providers import build_planner_provider

        return build_planner_provider(name, _settings)

    @property
    def router_name(self) -> str:
        return f"query_planner_{self._provider_name}"

    @property
    def last_fallback_reason(self) -> str | None:
        """Exception class name from the most recent ``plan()`` call, or None.

        Reset to None at the start of every ``plan()`` invocation; set to the
        exception class name only if fallback to LocalRuleProvider was
        triggered on that call.
        """
        return self._last_fallback_reason

    def plan(self, normalized_query: str) -> PlannerOutput:
        self._last_fallback_reason = None

        if self._cache_enabled and normalized_query in self._cache:
            return self._cache[normalized_query]

        try:
            output = self._impl.plan(normalized_query)
        except Exception as exc:
            # Lazy import to avoid pulling providers at module load.
            from app.query.providers.errors import PlannerProviderError

            if not isinstance(exc, PlannerProviderError):
                raise
            self._last_fallback_reason = type(exc).__name__
            output = self._fallback.plan(normalized_query)

        if self._cache_enabled:
            self._cache[normalized_query] = output

        return output


def _extract_lexical_terms(query: str) -> list[str]:
    terms = [query]
    if len(query) > 2:
        for index in range(len(query) - 1):
            bigram = query[index : index + 2]
            if bigram not in terms:
                terms.append(bigram)
    if len(query) > 4:
        for index in range(len(query) - 2):
            trigram = query[index : index + 3]
            if trigram not in terms:
                terms.append(trigram)
    return terms
