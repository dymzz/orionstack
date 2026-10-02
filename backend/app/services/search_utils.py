from __future__ import annotations

from typing import Any

from app.schemas.response import RetrievalCandidateSummary

ELASTIC_FAQ_PREFERENCE_MAX_SCORE_GAP = 0.35
CLARIFICATION_MAX_RERANK_SCORE_GAP = 0.15
SCOPED_HYBRID_RERANK_SIZE = 5
UNSCOPED_HYBRID_RERANK_SIZE = 12


def select_elastic_hit(hits) -> Any:
    best = hits[0]
    if best.source_kind == "faq":
        return best

    faq_candidate = next(
        (
            hit
            for hit in hits
            if hit.source_kind == "faq" and (hit.answer or hit.body_text)
        ),
        None,
    )
    if faq_candidate is None:
        return best

    score_gap = best.score - faq_candidate.score
    if score_gap <= ELASTIC_FAQ_PREFERENCE_MAX_SCORE_GAP:
        return faq_candidate
    return best


def select_reranked_hit(reranked_hits) -> Any | None:
    accepted_hits = [
        item
        for item in reranked_hits
        if item.accept and (item.hit.answer or item.hit.body_text)
    ]
    if not accepted_hits:
        return None

    best = accepted_hits[0]
    if best.hit.source_kind == "faq":
        return best

    faq_candidate = next(
        (item for item in accepted_hits if item.hit.source_kind == "faq"),
        None,
    )
    if faq_candidate is None:
        return best

    score_gap = best.rerank_score - faq_candidate.rerank_score
    if score_gap <= ELASTIC_FAQ_PREFERENCE_MAX_SCORE_GAP:
        return faq_candidate
    return best


def summarize_lexical_hits(
    hits, *, limit: int = 3
) -> list[RetrievalCandidateSummary]:
    return [
        RetrievalCandidateSummary(
            unit_id=hit.unit_id,
            score=float(hit.score),
            source_kind=hit.source_kind,
        )
        for hit in hits[:limit]
    ]


def summarize_hybrid_hits(
    hits, *, limit: int = 3
) -> tuple[
    list[RetrievalCandidateSummary],
    list[RetrievalCandidateSummary],
    list[RetrievalCandidateSummary],
]:
    lexical_topk = [
        RetrievalCandidateSummary(
            unit_id=hit.unit_id,
            score=float(hit.bm25_score or 0.0),
            source_kind=hit.source_kind,
        )
        for hit in sorted(
            (item for item in hits if item.lexical_rank is not None),
            key=lambda item: item.lexical_rank or 0,
        )[:limit]
    ]
    vector_topk = [
        RetrievalCandidateSummary(
            unit_id=hit.unit_id,
            score=float(hit.vector_score or 0.0),
            source_kind=hit.source_kind,
        )
        for hit in sorted(
            (item for item in hits if item.vector_rank is not None),
            key=lambda item: item.vector_rank or 0,
        )[:limit]
    ]
    rrf_topk = [
        RetrievalCandidateSummary(
            unit_id=hit.unit_id,
            score=float(hit.score),
            source_kind=hit.source_kind,
            lexical_dominance_applied=hit.lexical_dominance_applied,
            vector_dominance_applied=hit.vector_dominance_applied,
        )
        for hit in sorted(hits, key=lambda item: item.rrf_rank)[:limit]
    ]
    return lexical_topk, vector_topk, rrf_topk


def summarize_rerank_decision(
    reranked_hit,
    *,
    reject_reason: str | None = None,
) -> dict[str, bool | float | int | str | None]:
    if reranked_hit is None:
        return {
            "rerank_accept": None,
            "rerank_score": None,
            "evidence_confidence": None,
            "evidence_span_count": None,
            "reject_reason": reject_reason,
        }

    return {
        "rerank_accept": reranked_hit.accept,
        "rerank_score": float(reranked_hit.rerank_score),
        "evidence_confidence": float(reranked_hit.evidence_confidence),
        "evidence_span_count": len(reranked_hit.evidence_spans),
        "reject_reason": reject_reason,
    }


def format_backend_warning(backend_warning) -> str | None:
    if backend_warning is None:
        return None
    return f"{backend_warning.failed_stage}_backend_soft_fallback:{backend_warning.cause_name}"


def combine_reject_reason(
    reject_reason: str | None,
    backend_warning,
) -> str | None:
    backend_reason = format_backend_warning(backend_warning)
    if backend_reason is None:
        return reject_reason
    if reject_reason is None:
        return backend_reason
    return f"{reject_reason};{backend_reason}"


def format_backend_soft_fallback_reason(backend_warning) -> str | None:
    if backend_warning is None:
        return None
    return f"{backend_warning.failed_stage}_backend_soft_fallback"