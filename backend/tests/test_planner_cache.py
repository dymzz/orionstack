"""QueryPlanner cache semantics (docs/2_8 §5.2).

Verifies that:
- When cache is enabled (default), identical ``normalized_query`` inputs hit
  the cache and do NOT re-invoke the primary provider.
- When cache is disabled, every call reaches the provider.
- Fallback results (LocalRule output after LLM exception) are ALSO cached, to
  avoid cascading failures re-hitting the primary provider (2_8 §5.2 "失败结果
  也进缓存防雪崩").
- Different queries do not collide in the cache.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.query.providers.errors import PlannerHttpError
from app.query.query_planner import PlannerOutput, QueryPlanner


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


@dataclass
class _CountingProvider:
    """Provider that tracks plan() invocation count; returns a canned output."""

    name: str = "qwen_api"
    output: PlannerOutput = field(
        default_factory=lambda: PlannerOutput(
            normalized_query="stub",
            domain_hint=None,
            lexical_terms=["stub"],
            planner_confidence=0.5,
        )
    )
    call_count: int = 0
    queries_seen: list[str] = field(default_factory=list)

    def plan(self, normalized_query: str) -> PlannerOutput:
        self.call_count += 1
        self.queries_seen.append(normalized_query)
        return self.output


@dataclass
class _RaisingCountingProvider:
    """Provider that tracks invocation count and always raises HttpError."""

    name: str = "qwen_api"
    call_count: int = 0

    def plan(self, normalized_query: str) -> PlannerOutput:
        self.call_count += 1
        raise PlannerHttpError("always fails")


def _planner_with_impl(impl, cache_enabled: bool = True) -> QueryPlanner:
    planner = QueryPlanner(provider="local", model="stub")
    planner._impl = impl  # type: ignore[attr-defined]
    planner._cache_enabled = cache_enabled  # type: ignore[attr-defined]
    # Reset the cache to avoid leakage from construction
    planner._cache = {}  # type: ignore[attr-defined]
    return planner


# ---------------------------------------------------------------------------
# Cache hit / miss semantics
# ---------------------------------------------------------------------------


class TestCacheEnabled:
    def test_same_query_hits_cache_on_second_call(self) -> None:
        impl = _CountingProvider()
        planner = _planner_with_impl(impl, cache_enabled=True)

        planner.plan("请假审批")
        planner.plan("请假审批")

        assert impl.call_count == 1  # second call served from cache

    def test_five_identical_calls_hit_provider_once(self) -> None:
        impl = _CountingProvider()
        planner = _planner_with_impl(impl, cache_enabled=True)

        for _ in range(5):
            planner.plan("同一查询")

        assert impl.call_count == 1

    def test_different_queries_bypass_cache(self) -> None:
        impl = _CountingProvider()
        planner = _planner_with_impl(impl, cache_enabled=True)

        planner.plan("查询 A")
        planner.plan("查询 B")
        planner.plan("查询 C")

        assert impl.call_count == 3
        assert impl.queries_seen == ["查询 A", "查询 B", "查询 C"]

    def test_cached_output_is_identical(self) -> None:
        impl = _CountingProvider()
        planner = _planner_with_impl(impl, cache_enabled=True)

        first = planner.plan("query")
        second = planner.plan("query")

        assert first == second


class TestCacheDisabled:
    def test_every_call_hits_provider(self) -> None:
        impl = _CountingProvider()
        planner = _planner_with_impl(impl, cache_enabled=False)

        planner.plan("query")
        planner.plan("query")
        planner.plan("query")

        assert impl.call_count == 3


# ---------------------------------------------------------------------------
# Fallback result caching (防雪崩)
# ---------------------------------------------------------------------------


class TestFallbackResultsAreCached:
    def test_second_call_after_fallback_does_not_retry_primary(self) -> None:
        """After primary fails and fallback serves, the cached fallback output
        is returned on subsequent calls — primary is NOT retried."""
        impl = _RaisingCountingProvider()
        planner = _planner_with_impl(impl, cache_enabled=True)

        first = planner.plan("一次失败的查询")
        assert planner.last_fallback_reason == "PlannerHttpError"
        assert impl.call_count == 1

        second = planner.plan("一次失败的查询")
        # last_fallback_reason resets to None because we didn't hit provider
        assert planner.last_fallback_reason is None
        # primary was NOT retried; cache served the fallback result
        assert impl.call_count == 1
        assert first == second

    def test_different_query_after_fallback_retries_primary(self) -> None:
        """Only identical queries are short-circuited — a new query still tries
        the primary provider (and will fail + fall back again)."""
        impl = _RaisingCountingProvider()
        planner = _planner_with_impl(impl, cache_enabled=True)

        planner.plan("query A")
        planner.plan("query B")

        assert impl.call_count == 2

    def test_many_identical_failing_calls_hit_primary_once(self) -> None:
        """Stampede protection: a flood of identical calls that would otherwise
        each retry the failing LLM all get served from the cache after the
        first attempt."""
        impl = _RaisingCountingProvider()
        planner = _planner_with_impl(impl, cache_enabled=True)

        for _ in range(20):
            planner.plan("storm query")

        assert impl.call_count == 1


# ---------------------------------------------------------------------------
# Cache is per-instance (not a class-level global)
# ---------------------------------------------------------------------------


class TestCacheIsolation:
    def test_cache_does_not_leak_across_planner_instances(self) -> None:
        impl_a = _CountingProvider()
        impl_b = _CountingProvider()
        planner_a = _planner_with_impl(impl_a, cache_enabled=True)
        planner_b = _planner_with_impl(impl_b, cache_enabled=True)

        planner_a.plan("shared query")
        planner_b.plan("shared query")

        # Both providers were each called exactly once
        assert impl_a.call_count == 1
        assert impl_b.call_count == 1
