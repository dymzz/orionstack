from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from elasticsearch import Elasticsearch


@dataclass(frozen=True)
class LexicalHit:
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


class RetrievalBackendError(RuntimeError):
    def __init__(self, stage: str, cause: Exception) -> None:
        self.stage = stage
        self.cause_name = cause.__class__.__name__
        super().__init__(f"{stage} backend search failed: {self.cause_name}")


class LexicalRetriever:
    def __init__(
        self, es: Elasticsearch, *, index_name: str = "knowledge_units_v1"
    ) -> None:
        self._es = es
        self._index_name = index_name

    def search(
        self,
        query: str,
        *,
        lexical_terms: list[str] | None = None,
        min_score: float = 0.1,
        business_domain: str | None = None,
        access_scope: str | None = None,
        lifecycle_status: str | None = None,
        size: int = 10,
    ) -> list[LexicalHit]:
        normalized = query.strip().lower()
        if not normalized:
            return []

        must_queries: list[dict[str, Any]] = [
            {
                "multi_match": {
                    "query": normalized,
                    "fields": ["question^3", "answer^2", "body_text", "keywords"],
                    "type": "best_fields",
                }
            }
        ]

        should_queries: list[dict[str, Any]] = []
        if lexical_terms:
            for term in lexical_terms:
                should_queries.append({"term": {"keywords": term}})

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
            "size": size,
            "query": {
                "bool": {
                    "must": must_queries,
                    "should": should_queries if should_queries else [],
                    "filter": filter_clauses,
                }
            },
            "min_score": min_score,
        }

        try:
            result = self._es.search(index=self._index_name, body=body)
        except Exception as error:
            raise RetrievalBackendError("lexical", error) from error

        hits: list[LexicalHit] = []
        for hit in result.get("hits", {}).get("hits", []):
            source = hit.get("_source", {})
            score = float(hit.get("_score", 0.0))
            hits.append(
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
                )
            )
        return hits
