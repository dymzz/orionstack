from __future__ import annotations

from hashlib import sha1
from math import sqrt
from typing import Any

from elasticsearch import Elasticsearch

from app.retrieval.lexical_retriever import LexicalHit, RetrievalBackendError

_VECTOR_DIMENSION = 64


class VectorRetriever:
    def __init__(
        self,
        es: Elasticsearch,
        *,
        index_name: str = "knowledge_units_v1",
        candidate_window_size: int = 50,
    ) -> None:
        self._es = es
        self._index_name = index_name
        self._candidate_window_size = candidate_window_size

    def search(
        self,
        query: str,
        *,
        min_score: float = 0.0,
        business_domain: str | None = None,
        access_scope: str | None = None,
        lifecycle_status: str | None = None,
        size: int = 10,
    ) -> list[LexicalHit]:
        normalized = query.strip().lower()
        if not normalized:
            return []

        filter_clauses: list[dict[str, Any]] = []
        if business_domain:
            filter_clauses.append({"term": {"business_domain": business_domain}})
        if access_scope:
            filter_clauses.append({"term": {"access_scope": access_scope}})
        if lifecycle_status:
            filter_clauses.append({"term": {"lifecycle_status": lifecycle_status}})
        else:
            filter_clauses.append({"term": {"lifecycle_status": "active"}})

        body: dict[str, Any] = {
            "size": max(size, self._candidate_window_size),
            "query": {"bool": {"filter": filter_clauses}},
        }

        try:
            result = self._es.search(index=self._index_name, body=body)
        except Exception as error:
            raise RetrievalBackendError("vector", error) from error

        query_vector = _text_to_unit_vector(normalized)
        scored_hits: list[LexicalHit] = []
        for hit in result.get("hits", {}).get("hits", []):
            source = hit.get("_source", {})
            candidate_text = " ".join(
                part
                for part in (
                    source.get("question", ""),
                    source.get("answer", ""),
                    source.get("body_text", ""),
                )
                if part
            )
            score = _cosine_similarity(query_vector, _text_to_unit_vector(candidate_text))
            if score < min_score:
                continue
            scored_hits.append(
                LexicalHit(
                    unit_id=source.get("unit_id", ""),
                    source_kind=source.get("source_kind", ""),
                    question=source.get("question", ""),
                    answer=source.get("answer", ""),
                    body_text=source.get("body_text", ""),
                    source_label=source.get("source_label", ""),
                    source_locator=source.get("source_locator", ""),
                    score=score,
                    business_domain=source.get("business_domain", ""),
                    document_type=source.get("document_type", ""),
                    source_type=source.get("source_type", ""),
                    access_scope=source.get("access_scope", ""),
                    lifecycle_status=source.get("lifecycle_status", ""),
                    source_record_id=source.get("source_record_id", ""),
                    import_batch_id=source.get("import_batch_id", ""),
                    unit_version=int(source.get("unit_version") or 1),
                    fresh_until=source.get("fresh_until", ""),
                    stale_after=source.get("stale_after", ""),
                )
            )

        scored_hits.sort(key=lambda item: item.score, reverse=True)
        return scored_hits[:size]


def _text_to_unit_vector(text: str) -> list[float]:
    vector = [0.0] * _VECTOR_DIMENSION
    for token in _tokenize(text):
        index = int(sha1(token.encode("utf-8")).hexdigest(), 16) % _VECTOR_DIMENSION
        vector[index] += 1.0

    magnitude = sqrt(sum(value * value for value in vector))
    if magnitude == 0.0:
        return vector
    return [value / magnitude for value in vector]


def _tokenize(text: str) -> list[str]:
    compact = "".join(text.lower().split())
    if not compact:
        return []

    tokens = [compact]
    if len(compact) > 1:
        for index in range(len(compact) - 1):
            tokens.append(compact[index : index + 2])
    if len(compact) > 2:
        for index in range(len(compact) - 2):
            tokens.append(compact[index : index + 3])
    return tokens


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    return sum(left_value * right_value for left_value, right_value in zip(left, right))
