from dataclasses import dataclass
from typing import Any

from app.storage.repositories.faq_repo import FAQRepository
from app.storage.repositories.chunk_repo import ChunkRepository


@dataclass(frozen=True)
class RetrievalHit:
    item: dict[str, Any]
    score: int
    matched_terms: tuple[str, ...]


class Retriever:
    def __init__(self, faq_repo: FAQRepository, chunk_repo: ChunkRepository) -> None:
        self._faq_repo = faq_repo
        self._chunk_repo = chunk_repo

    def search(
        self, query: str, *, min_score: int, document_ids: list[str] | None = None
    ) -> RetrievalHit | None:
        tokens = self._tokenize(query)
        if not tokens:
            return None

        compact_query = self._compact_query(query)
        allowed_document_ids = {
            document_id for document_id in (document_ids or []) if document_id
        }

        document_hit = self._search_document_chunks(
            tokens, compact_query, allowed_document_ids or None
        )
        if document_hit is not None and document_hit.score >= min_score:
            return document_hit

        if allowed_document_ids:
            return document_hit

        faq_hit = self._search_faq(tokens, compact_query)
        if faq_hit is not None:
            return faq_hit

        return document_hit

    def _search_document_chunks(
        self,
        tokens: list[str],
        compact_query: str,
        allowed_document_ids: set[str] | None,
    ) -> RetrievalHit | None:
        best_hit: RetrievalHit | None = None
        best_score = 0

        for item in self._chunk_repo.list_all():
            document_id = str(item.get("document_id", ""))
            if (
                allowed_document_ids is not None
                and document_id not in allowed_document_ids
            ):
                continue

            text = str(item.get("text", "")).lower()
            filename = str(item.get("filename", "")).lower()
            snippet = str(item.get("snippet", "")).lower()
            haystack = " ".join([text, filename, snippet]).lower()
            matched_terms = tuple(
                sorted({token for token in tokens if token in haystack})
            )
            score = len(matched_terms)

            compact_text = text.replace(" ", "")
            if (
                compact_query
                and len(compact_query) >= 3
                and compact_query in compact_text
            ):
                score += 2

            if compact_query and compact_query in filename.replace(" ", ""):
                score += 1

            if score > best_score:
                best_score = score
                best_hit = RetrievalHit(
                    item={
                        "id": item["chunk_id"],
                        "answer": item["text"],
                        "source_label": item.get(
                            "source_label", item.get("filename", "Document")
                        ),
                        "source_locator": item.get("source_locator", item["chunk_id"]),
                        "snippet": item.get("snippet", item["text"][:160]),
                    },
                    score=score,
                    matched_terms=matched_terms,
                )

        return best_hit if best_hit is not None and best_hit.score > 0 else None

    def _search_faq(self, tokens: list[str], compact_query: str) -> RetrievalHit | None:
        best_hit: RetrievalHit | None = None
        best_score = 0

        for item in self._faq_repo.list_all():
            question = str(item["question"]).lower()
            keywords = [str(keyword).lower() for keyword in item.get("keywords", [])]
            haystack = " ".join(
                [
                    question,
                    str(item["answer"]).lower(),
                    " ".join(keywords),
                ]
            ).lower()
            matched_terms = tuple(
                sorted({token for token in tokens if token in haystack})
            )
            score = len(matched_terms)

            if (
                compact_query
                and len(compact_query) >= 3
                and compact_query in question.replace(" ", "")
            ):
                score += 2

            if compact_query and any(
                compact_query == keyword.replace(" ", "") for keyword in keywords
            ):
                score += 1

            if score > best_score:
                best_score = score
                best_hit = RetrievalHit(
                    item=item, score=score, matched_terms=matched_terms
                )

        return best_hit if best_hit is not None and best_hit.score > 0 else None

    @staticmethod
    def _tokenize(query: str) -> list[str]:
        query = (
            query.lower()
            .replace("？", " ")
            .replace("?", " ")
            .replace("，", " ")
            .replace(",", " ")
        )
        tokens = [token.strip() for token in query.split() if token.strip()]
        if len(tokens) > 1:
            return tokens

        compact = tokens[0] if tokens else query.strip()
        if not compact:
            return []

        if any(ord(char) > 127 for char in compact) and len(compact) > 2:
            pieces = [compact[i : i + 2] for i in range(len(compact) - 1)]
            return list(dict.fromkeys([compact, *pieces]))

        return [compact]

    @staticmethod
    def _compact_query(query: str) -> str:
        return (
            query.lower()
            .replace("？", "")
            .replace("?", "")
            .replace("，", "")
            .replace(",", "")
            .replace(" ", "")
            .strip()
        )
