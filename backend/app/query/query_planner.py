from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PlannerOutput:
    normalized_query: str
    domain_hint: str | None
    lexical_terms: list[str]
    planner_confidence: float


class QueryPlanner:
    _HR_DOMAIN_KEYWORDS = (
        "hr",
        "人事",
        "请假",
        "休假",
        "病假",
        "年假",
        "调休",
        "考勤",
        "入职",
        "离职",
        "福利",
        "证明",
    )
    _LEAVE_KEYWORDS = ("请假", "休假", "病假", "年假", "调休")
    _MATERIAL_KEYWORDS = ("材料", "证明", "医院", "单据")
    _PROGRESS_KEYWORDS = ("进度", "状态", "审批", "记录", "查询")

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

        domain_hint = self._infer_domain_hint(query)
        lexical_terms = self._build_lexical_terms(query, domain_hint)
        planner_confidence = 0.88 if domain_hint is not None else 0.05

        return PlannerOutput(
            normalized_query=query,
            domain_hint=domain_hint,
            lexical_terms=lexical_terms,
            planner_confidence=planner_confidence,
        )

    @classmethod
    def _infer_domain_hint(cls, query: str) -> str | None:
        lowered_query = query.lower()
        if any(term in lowered_query for term in cls._HR_DOMAIN_KEYWORDS):
            return "hr"
        return None

    @classmethod
    def _build_lexical_terms(cls, query: str, domain_hint: str | None) -> list[str]:
        terms = _extract_lexical_terms(query)
        if domain_hint != "hr":
            return terms

        extra_terms: list[str] = []
        if any(term in query for term in cls._LEAVE_KEYWORDS):
            extra_terms.extend(["请假", "审批"])
        if any(term in query for term in cls._MATERIAL_KEYWORDS):
            extra_terms.extend(["材料", "证明"])
        if any(term in query for term in cls._PROGRESS_KEYWORDS):
            extra_terms.extend(["进度", "记录"])
        return _merge_terms(terms, extra_terms)


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


def _merge_terms(base_terms: list[str], extra_terms: list[str]) -> list[str]:
    merged = list(base_terms)
    for term in extra_terms:
        if term and term not in merged:
            merged.append(term)
    return merged
