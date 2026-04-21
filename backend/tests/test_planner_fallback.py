"""QueryPlanner fallback semantics (docs/2_8 §5.1).

Verifies that:
- Any PlannerProviderError subclass raised by the primary provider triggers
  fallback to LocalRuleProvider.
- ``last_fallback_reason`` is set to the exception class name when fallback
  occurs, and reset to None at the start of every ``plan()`` call.
- Non-PlannerProviderError exceptions propagate (not a planner debt, so
  crashing loudly is correct).
- Successful primary calls leave ``last_fallback_reason`` at None.

Tests inject fake providers via monkey-patching ``QueryPlanner._impl`` after
construction. This is intentional: QueryPlanner's public constructor only
accepts registered provider names ("local" / "qwen_api"); the _impl slot is
the documented test hook.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.query.providers.errors import (
    PlannerHttpError,
    PlannerParseError,
    PlannerProviderError,
    PlannerSchemaError,
    PlannerTimeoutError,
)
from app.query.query_planner import PlannerOutput, QueryPlanner


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


@dataclass
class _RaisingProvider:
    """Provider that raises the given exception on every plan() call."""

    name: str
    exc: Exception

    def plan(self, normalized_query: str) -> PlannerOutput:
        raise self.exc


@dataclass
class _SuccessProvider:
    """Provider that returns a canned output, tracking call count."""

    name: str
    output: PlannerOutput
    call_count: int = 0

    def plan(self, normalized_query: str) -> PlannerOutput:
        self.call_count += 1
        return self.output


def _fresh_planner() -> QueryPlanner:
    """Construct a planner with cache disabled to isolate fallback semantics."""
    planner = QueryPlanner(provider="local", model="stub")
    # Disable cache so each plan() call hits the provider
    planner._cache_enabled = False  # type: ignore[attr-defined]
    return planner


# ---------------------------------------------------------------------------
# Fallback on each exception type
# ---------------------------------------------------------------------------


class TestFallbackOnProviderErrors:
    @pytest.mark.parametrize(
        "exc_class",
        [
            PlannerTimeoutError,
            PlannerHttpError,
            PlannerParseError,
            PlannerSchemaError,
        ],
    )
    def test_provider_error_triggers_local_fallback(self, exc_class) -> None:
        planner = _fresh_planner()
        planner._impl = _RaisingProvider(name="qwen_api", exc=exc_class("boom"))  # type: ignore[attr-defined]

        output = planner.plan("请假审批")

        # Fallback to LocalRuleProvider produces a valid PlannerOutput
        assert isinstance(output, PlannerOutput)
        assert output.normalized_query == "请假审批"
        # last_fallback_reason records the exception class name
        assert planner.last_fallback_reason == exc_class.__name__

    def test_base_class_also_triggers_fallback(self) -> None:
        planner = _fresh_planner()
        planner._impl = _RaisingProvider(  # type: ignore[attr-defined]
            name="qwen_api", exc=PlannerProviderError("generic")
        )

        output = planner.plan("请假审批")
        assert isinstance(output, PlannerOutput)
        assert planner.last_fallback_reason == "PlannerProviderError"


# ---------------------------------------------------------------------------
# Non-PlannerProviderError propagation
# ---------------------------------------------------------------------------


class TestNonProviderErrorsPropagate:
    def test_value_error_propagates(self) -> None:
        planner = _fresh_planner()
        planner._impl = _RaisingProvider(name="qwen_api", exc=ValueError("bug"))  # type: ignore[attr-defined]

        with pytest.raises(ValueError, match="bug"):
            planner.plan("query")

    def test_type_error_propagates(self) -> None:
        planner = _fresh_planner()
        planner._impl = _RaisingProvider(name="qwen_api", exc=TypeError("oops"))  # type: ignore[attr-defined]

        with pytest.raises(TypeError, match="oops"):
            planner.plan("query")

    def test_runtime_error_propagates(self) -> None:
        planner = _fresh_planner()
        planner._impl = _RaisingProvider(name="qwen_api", exc=RuntimeError("x"))  # type: ignore[attr-defined]

        with pytest.raises(RuntimeError):
            planner.plan("query")


# ---------------------------------------------------------------------------
# last_fallback_reason lifecycle
# ---------------------------------------------------------------------------


class TestLastFallbackReasonLifecycle:
    def test_none_on_fresh_planner(self) -> None:
        planner = _fresh_planner()
        assert planner.last_fallback_reason is None

    def test_none_after_successful_primary_call(self) -> None:
        planner = _fresh_planner()
        canned = PlannerOutput(
            normalized_query="x",
            domain_hint="hr",
            lexical_terms=["x"],
            planner_confidence=0.9,
        )
        planner._impl = _SuccessProvider(name="qwen_api", output=canned)  # type: ignore[attr-defined]

        planner.plan("x")
        assert planner.last_fallback_reason is None

    def test_resets_between_calls(self) -> None:
        planner = _fresh_planner()
        canned = PlannerOutput(
            normalized_query="y",
            domain_hint=None,
            lexical_terms=["y"],
            planner_confidence=0.5,
        )

        # First call: fallback triggered
        planner._impl = _RaisingProvider(  # type: ignore[attr-defined]
            name="qwen_api", exc=PlannerTimeoutError("first")
        )
        planner.plan("first query")
        assert planner.last_fallback_reason == "PlannerTimeoutError"

        # Swap to success and call again — reason must reset
        planner._impl = _SuccessProvider(name="qwen_api", output=canned)  # type: ignore[attr-defined]
        planner.plan("second query")
        assert planner.last_fallback_reason is None

    def test_updates_on_subsequent_failure(self) -> None:
        planner = _fresh_planner()

        # First: timeout
        planner._impl = _RaisingProvider(  # type: ignore[attr-defined]
            name="qwen_api", exc=PlannerTimeoutError("t")
        )
        planner.plan("q1")
        assert planner.last_fallback_reason == "PlannerTimeoutError"

        # Second: http error — reason updates to new class name
        planner._impl = _RaisingProvider(  # type: ignore[attr-defined]
            name="qwen_api", exc=PlannerHttpError("h")
        )
        planner.plan("q2")
        assert planner.last_fallback_reason == "PlannerHttpError"


# ---------------------------------------------------------------------------
# Fallback output quality — it comes from LocalRuleProvider
# ---------------------------------------------------------------------------


class TestFallbackOutputIsFromLocalRule:
    def test_fallback_output_matches_local_rule_direct_call(self) -> None:
        """Fallback output must be indistinguishable from calling LocalRule directly."""
        from app.query.query_planner import LocalRuleProvider

        query = "请假审批进度怎么查看？"

        # Planner with a failing provider → falls back to LocalRule
        planner = _fresh_planner()
        planner._impl = _RaisingProvider(  # type: ignore[attr-defined]
            name="qwen_api", exc=PlannerHttpError("down")
        )
        fallback_output = planner.plan(query)

        # Direct LocalRule call for comparison
        direct_output = LocalRuleProvider().plan(query)

        assert fallback_output == direct_output
