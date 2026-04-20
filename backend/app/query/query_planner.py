from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PlannerOutput:
    normalized_query: str
    domain_hint: str | None
    lexical_terms: list[str]
    planner_confidence: float


class QueryPlanner:
    def __init__(self, *, provider: str = "local", model: str = "") -> None:
        self._provider = provider
        self._model = model

    @property
    def router_name(self) -> str:
        return "query_planner_local"

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
