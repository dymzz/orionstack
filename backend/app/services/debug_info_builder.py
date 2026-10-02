from __future__ import annotations

from typing import Any

from app.query.query_planner import PlannerOutput
from app.schemas.response import DebugInfo, RetrievalCandidateSummary


def build_debug_info(
    enabled: bool,
    normalized_query: str,
    route_result: str,
    chunk_ids: list[str],
    *,
    router_used: str,
    route_confidence: float | None,
    retrieval_score: float | None = None,
    fusion_score: float | None = None,
    fallback_reason: str | None = None,
    planner_output: PlannerOutput | None = None,
    retrieval_mode: str | None = None,
    lexical_topk: list[RetrievalCandidateSummary] | None = None,
    vector_topk: list[RetrievalCandidateSummary] | None = None,
    rrf_topk: list[RetrievalCandidateSummary] | None = None,
    rerank_accept: bool | None = None,
    rerank_score: float | None = None,
    evidence_confidence: float | None = None,
    evidence_span_count: int | None = None,
    reject_reason: str | None = None,
    source_record_id: str | None = None,
    import_batch_id: str | None = None,
    unit_version: int | None = None,
    source_updated_at: str | None = None,
    source_record_status: str | None = None,
    dynamic_query_key: str | None = None,
    freshness_status: str | None = None,
) -> DebugInfo | None:
    if not enabled:
        return None
    return DebugInfo(
        normalized_query=normalized_query,
        route_result=route_result,
        router_used=router_used,
        retrieved_chunks=chunk_ids,
        route_confidence=route_confidence,
        retrieval_score=retrieval_score,
        fusion_score=fusion_score,
        fallback_reason=fallback_reason,
        domain_hint=None if planner_output is None else planner_output.domain_hint,
        lexical_terms=None if planner_output is None else planner_output.lexical_terms,
        planner_confidence=None
        if planner_output is None
        else planner_output.planner_confidence,
        retrieval_mode=retrieval_mode,
        lexical_topk=lexical_topk,
        vector_topk=vector_topk,
        rrf_topk=rrf_topk,
        rerank_accept=rerank_accept,
        rerank_score=rerank_score,
        evidence_confidence=evidence_confidence,
        evidence_span_count=evidence_span_count,
        reject_reason=reject_reason,
        source_record_id=source_record_id,
        import_batch_id=import_batch_id,
        unit_version=unit_version,
        source_updated_at=source_updated_at,
        source_record_status=source_record_status,
        dynamic_query_key=dynamic_query_key,
        freshness_status=freshness_status,
    )


def hit_provenance_kwargs(hit) -> dict[str, Any]:
    return {
        "source_record_id": getattr(hit, "source_record_id", "") or None,
        "import_batch_id": getattr(hit, "import_batch_id", "") or None,
        "unit_version": int(getattr(hit, "unit_version", 1) or 1),
        "source_updated_at": getattr(hit, "source_updated_at", "") or None,
    }


def item_provenance_kwargs(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_record_id": item.get("source_record_id") or None,
        "import_batch_id": item.get("import_batch_id") or None,
        "unit_version": int(item.get("unit_version") or 1),
        "source_updated_at": item.get("source_updated_at") or None,
    }