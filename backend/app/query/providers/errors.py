"""Planner provider exception taxonomy.

Any subclass of PlannerProviderError raised by a provider's ``plan()`` method
is caught by QueryPlanner and triggers fallback to LocalRuleProvider. See
docs/2_8_planner_llm_integration.md §4.2 for the full taxonomy.
"""

from __future__ import annotations


class PlannerProviderError(Exception):
    """Base class for all planner provider failures that trigger fallback."""


class PlannerTimeoutError(PlannerProviderError):
    """The provider call timed out."""


class PlannerHttpError(PlannerProviderError):
    """HTTP connection failed or returned non-2xx status."""


class PlannerParseError(PlannerProviderError):
    """Response body or the message content could not be parsed as JSON."""


class PlannerSchemaError(PlannerProviderError):
    """Parsed JSON did not match the expected PlannerOutput schema."""
