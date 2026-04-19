from __future__ import annotations

from dataclasses import dataclass

from app.retrieval.lexical_retriever import LexicalHit, LexicalRetriever
from app.retrieval.vector_retriever import VectorRetriever

RRF_RANK_CONSTANT = 60
RRF_RANK_WINDOW_SIZE = 50


@dataclass(frozen=True)
class HybridHit:
    unit_id: str
    source_kind: str
    question: str
    answer: str
    body_text: str
    source_label: str
    source_locator: str
    score: float
    business_domain: str
    document_type: str
    source_type: str
    access_scope: str
    lifecycle_status: str
    bm25_score: float | None
    vector_score: float | None
    lexical_rank: int | None
    vector_rank: int | None
    rrf_rank: int


class HybridRetriever:
    def __init__(
        self,
        lexical_retriever: LexicalRetriever,
        vector_retriever: VectorRetriever,
        *,
        rank_constant: int = RRF_RANK_CONSTANT,
        rank_window_size: int = RRF_RANK_WINDOW_SIZE,
    ) -> None:
        self._lexical_retriever = lexical_retriever
        self._vector_retriever = vector_retriever
        self._rank_constant = rank_constant
        self._rank_window_size = rank_window_size

    def search(
        self,
        *,
        lexical_query: str,
        vector_query: str,
        lexical_terms: list[str] | None = None,
        business_domain: str | None = None,
        access_scope: str | None = None,
        lifecycle_status: str | None = None,
        size: int = 10,
    ) -> list[HybridHit]:
        lexical_hits = self._lexical_retriever.search(
            lexical_query,
            lexical_terms=lexical_terms,
            min_score=0.1,
            business_domain=business_domain,
            access_scope=access_scope,
            lifecycle_status=lifecycle_status,
            size=max(size, self._rank_window_size),
        )
        vector_hits = self._vector_retriever.search(
            vector_query,
            min_score=0.0,
            business_domain=business_domain,
            access_scope=access_scope,
            lifecycle_status=lifecycle_status,
            size=max(size, self._rank_window_size),
        )

        return self._fuse_hits(lexical_hits, vector_hits, size=size)

    def _fuse_hits(
        self, lexical_hits: list[LexicalHit], vector_hits: list[LexicalHit], *, size: int
    ) -> list[HybridHit]:
        lexical_rank_map = {
            hit.unit_id: rank
            for rank, hit in enumerate(lexical_hits[: self._rank_window_size], start=1)
        }
        vector_rank_map = {
            hit.unit_id: rank
            for rank, hit in enumerate(vector_hits[: self._rank_window_size], start=1)
        }
        lexical_hit_map = {hit.unit_id: hit for hit in lexical_hits}
        vector_hit_map = {hit.unit_id: hit for hit in vector_hits}

        hybrid_hits: list[HybridHit] = []
        for unit_id in set(lexical_hit_map) | set(vector_hit_map):
            lexical_hit = lexical_hit_map.get(unit_id)
            vector_hit = vector_hit_map.get(unit_id)
            base_hit = lexical_hit or vector_hit
            if base_hit is None:
                continue

            lexical_rank = lexical_rank_map.get(unit_id)
            vector_rank = vector_rank_map.get(unit_id)
            rrf_score = 0.0
            if lexical_rank is not None:
                rrf_score += 1.0 / (self._rank_constant + lexical_rank)
            if vector_rank is not None:
                rrf_score += 1.0 / (self._rank_constant + vector_rank)

            hybrid_hits.append(
                HybridHit(
                    unit_id=base_hit.unit_id,
                    source_kind=base_hit.source_kind,
                    question=base_hit.question,
                    answer=base_hit.answer,
                    body_text=base_hit.body_text,
                    source_label=base_hit.source_label,
                    source_locator=base_hit.source_locator,
                    score=rrf_score,
                    business_domain=base_hit.business_domain,
                    document_type=base_hit.document_type,
                    source_type=base_hit.source_type,
                    access_scope=base_hit.access_scope,
                    lifecycle_status=base_hit.lifecycle_status,
                    bm25_score=None if lexical_hit is None else lexical_hit.score,
                    vector_score=None if vector_hit is None else vector_hit.score,
                    lexical_rank=lexical_rank,
                    vector_rank=vector_rank,
                    rrf_rank=0,
                )
            )

        hybrid_hits.sort(
            key=lambda item: (
                item.score,
                item.bm25_score or 0.0,
                item.vector_score or 0.0,
            ),
            reverse=True,
        )

        ranked_hits: list[HybridHit] = []
        for rank, hit in enumerate(hybrid_hits[:size], start=1):
            ranked_hits.append(
                HybridHit(
                    unit_id=hit.unit_id,
                    source_kind=hit.source_kind,
                    question=hit.question,
                    answer=hit.answer,
                    body_text=hit.body_text,
                    source_label=hit.source_label,
                    source_locator=hit.source_locator,
                    score=hit.score,
                    business_domain=hit.business_domain,
                    document_type=hit.document_type,
                    source_type=hit.source_type,
                    access_scope=hit.access_scope,
                    lifecycle_status=hit.lifecycle_status,
                    bm25_score=hit.bm25_score,
                    vector_score=hit.vector_score,
                    lexical_rank=hit.lexical_rank,
                    vector_rank=hit.vector_rank,
                    rrf_rank=rank,
                )
            )
        return ranked_hits
