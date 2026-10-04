"""Optional evaluators. Import and construct only when a processing policy selects them."""

import json
import math

from app.decision.jev import JevClient
from app.knowledge.contracts import AccessContext, QueryContext
from app.retrieval.raw_contracts import RawRetrievalRecord, RetrievalEvaluation
from app.retrieval.raw_pipeline import ProcessorResult


class ScoreRerankProcessor:
    """An injected scorer sees raw query/text; its scores stay in the evaluation layer."""
    name = "reranker"

    def __init__(self, scorer, model: str) -> None:
        if not model.strip():
            raise ValueError("Reranker model/version is required")
        self.scorer = scorer
        self.model = model

    def configuration(self) -> dict:
        return {"model": self.model, "score_order": "descending"}

    def process(self, record: RawRetrievalRecord, candidate_ids: tuple[str, ...],
                access: AccessContext) -> ProcessorResult:
        record.require_access(access)
        by_id = {candidate.candidate_id: candidate for candidate in record.candidates}
        if not candidate_ids:
            return ProcessorResult(selected_candidate_ids=())
        scores = self.scorer(record.event.query, tuple(by_id[identity].text for identity in candidate_ids))
        if len(scores) != len(candidate_ids) or any(isinstance(score, bool) or not isinstance(score, (int, float))
                                                   or not math.isfinite(score) for score in scores):
            raise ValueError("Reranker must return one finite score per candidate in input order")
        ordering = sorted(zip(candidate_ids, scores), key=lambda item: (-item[1], by_id[item[0]].rank))
        return ProcessorResult(
            selected_candidate_ids=tuple(identity for identity, _ in ordering),
            evaluations=tuple(RetrievalEvaluation(candidate_id=identity, evaluator="reranker",
                                                  evaluator_version=self.model, decision="ranked", score=score)
                              for identity, score in zip(candidate_ids, scores)),
        )


class RuleRetrievalProcessor:
    """Optional relevance rules; mandatory authorization is already enforced by SQL."""
    name = "rule"

    def __init__(self, predicate, version: str) -> None:
        if not version.strip():
            raise ValueError("Rule version is required")
        self.predicate = predicate
        self.version = version

    def configuration(self) -> dict:
        return {"version": self.version}

    def process(self, record: RawRetrievalRecord, candidate_ids: tuple[str, ...],
                access: AccessContext) -> ProcessorResult:
        record.require_access(access)
        by_id = {candidate.candidate_id: candidate for candidate in record.candidates}
        selected = []
        evaluations = []
        for identity in candidate_ids:
            decision = self.predicate(record.event.query, by_id[identity])
            if not isinstance(decision, bool):
                raise ValueError("Rule must return a boolean relevance decision")
            if decision:
                selected.append(identity)
            evaluations.append(RetrievalEvaluation(candidate_id=identity, evaluator="rule",
                                                   evaluator_version=self.version,
                                                   decision="eligible" if decision else "excluded"))
        return ProcessorResult(selected_candidate_ids=tuple(selected), evaluations=tuple(evaluations))


class JevRetrievalProcessor:
    name = "jev"

    def __init__(self, client: JevClient | None = None, *, min_relevance: float = 1.5,
                 min_support: float = 0.5) -> None:
        if (not math.isfinite(min_relevance) or not 0 <= min_relevance <= 3
                or not math.isfinite(min_support) or not 0 <= min_support <= 1):
            raise ValueError("Invalid Jev evidence thresholds")
        self.client = client or JevClient()
        self.min_relevance = min_relevance
        self.min_support = min_support

    def configuration(self) -> dict:
        return {"model": self.client.settings.jev_model,
                "min_relevance": self.min_relevance, "min_support": self.min_support,
                "rubric": "relevance_4_levels_support_v1"}

    def process(self, record: RawRetrievalRecord, candidate_ids: tuple[str, ...],
                access: AccessContext) -> ProcessorResult:
        record.require_access(access)
        by_id = {candidate.candidate_id: candidate for candidate in record.candidates}
        selected = []
        evaluations = []
        for start in range(0, len(candidate_ids), 20):
            batch_ids = candidate_ids[start:start + 20]
            evidence = tuple(by_id[identity].evidence(record.event.tenant_id, record.event.created_at)
                             for identity in batch_ids)
            judgments, result = self.client.judge_evidence(QueryContext(query=record.event.query), evidence, access)
            if result is None:
                continue
            for judgment in judgments:
                eligible = judgment.relevance.score >= self.min_relevance and judgment.support.noul >= self.min_support
                evaluations.append(RetrievalEvaluation(
                    candidate_id=judgment.evidence_id, evaluator="jev", evaluator_version=result.model,
                    decision="eligible" if eligible else "excluded", score=judgment.relevance.score,
                    reason="relevance_and_support_rubric",
                    details_json=json.dumps({"relevance": judgment.relevance.model_dump(),
                                             "support": judgment.support.model_dump(),
                                             "usage": result.usage.model_dump()}),
                ))
                if eligible:
                    selected.append((judgment.evidence_id, judgment.relevance.score, judgment.support.noul))
        selected.sort(key=lambda item: (-item[1], -item[2], by_id[item[0]].rank))
        return ProcessorResult(selected_candidate_ids=tuple(item[0] for item in selected),
                               evaluations=tuple(evaluations))
