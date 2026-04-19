from __future__ import annotations

from dataclasses import dataclass

from app.retrieval.evidence_extractor import EvidenceExtractor, EvidenceSpan
from app.retrieval.hybrid_retriever import HybridHit


@dataclass(frozen=True)
class RerankHit:
    hit: HybridHit
    rerank_score: float
    evidence_spans: list[EvidenceSpan]
    evidence_confidence: float
    accept: bool


class Reranker:
    _FAQ_EVIDENCE_BONUS = 0.03
    _FAQ_SOURCE_BONUS = 0.01
    _DOCUMENT_PENALTY = 0.01
    _ACCEPT_EVIDENCE_THRESHOLD = 0.15

    def __init__(self, evidence_extractor: EvidenceExtractor | None = None) -> None:
        self._evidence_extractor = (
            EvidenceExtractor() if evidence_extractor is None else evidence_extractor
        )

    def rerank(self, query: str, hits: list[HybridHit], *, top_n: int = 3) -> list[RerankHit]:
        reranked_hits: list[RerankHit] = []
        for hit in hits[:top_n]:
            evidence_result = self._evidence_extractor.extract(
                query, hit.answer or hit.body_text
            )
            score = hit.score + evidence_result.evidence_confidence
            if hit.source_kind == "faq":
                score += self._FAQ_SOURCE_BONUS
            else:
                score -= self._DOCUMENT_PENALTY

            if hit.source_kind == "faq" and evidence_result.evidence_spans:
                score += self._FAQ_EVIDENCE_BONUS

            reranked_hits.append(
                RerankHit(
                    hit=hit,
                    rerank_score=score,
                    evidence_spans=evidence_result.evidence_spans,
                    evidence_confidence=evidence_result.evidence_confidence,
                    accept=evidence_result.evidence_confidence
                    >= self._ACCEPT_EVIDENCE_THRESHOLD,
                )
            )

        reranked_hits.sort(
            key=lambda item: (
                item.rerank_score,
                item.evidence_confidence,
                item.hit.bm25_score or 0.0,
                item.hit.vector_score or 0.0,
            ),
            reverse=True,
        )
        return reranked_hits
