import json
import re
from dataclasses import dataclass
from typing import Any

from app.storage.repositories.faq_repo import FAQRepository
from app.storage.repositories.chunk_repo import ChunkRepository

_PHASE3_LOCAL_METADATA_FIELDS = (
    "business_domain",
    "source_record_id",
    "import_batch_id",
    "unit_version",
    "source_updated_at",
    "fresh_until",
    "stale_after",
)


@dataclass(frozen=True)
class RetrievalHit:
    item: dict[str, Any]
    score: int
    matched_terms: tuple[str, ...]


@dataclass(frozen=True)
class _DocumentCandidate:
    item: dict[str, Any]
    search_text: str
    compact_text: str
    score_bonus: int


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
            if item.get("lifecycle_status", "active") != "active":
                continue

            document_id = str(item.get("document_id", ""))
            if (
                allowed_document_ids is not None
                and document_id not in allowed_document_ids
            ):
                continue

            candidate = self._build_document_candidate(item)
            text = candidate.search_text.lower()
            filename = str(item.get("filename", "")).lower()
            haystack = " ".join([text, filename]).lower()
            matched_terms = tuple(
                sorted({token for token in tokens if token in haystack})
            )
            score = len(matched_terms) + candidate.score_bonus

            if (
                compact_query
                and len(compact_query) >= 3
                and compact_query in candidate.compact_text
            ):
                score += 2

            if compact_query and compact_query in filename.replace(" ", ""):
                score += 1

            if score > best_score:
                best_score = score
                best_hit = RetrievalHit(
                    item=candidate.item,
                    score=score,
                    matched_terms=matched_terms,
                )

        return best_hit if best_hit is not None and best_hit.score > 0 else None

    def _build_document_candidate(self, item: dict[str, Any]) -> _DocumentCandidate:
        text = str(item.get("text", ""))
        extracted = self._extract_structured_faq(text)
        if extracted is None:
            snippet = str(item.get("snippet", text[:160]))
            search_text = " ".join(
                part for part in (text, snippet) if part
            ).strip()
            return _DocumentCandidate(
                item={
                    "id": item["chunk_id"],
                    "answer": text,
                    "source_label": item.get(
                        "source_label", item.get("filename", "Document")
                    ),
                    "source_locator": item.get("source_locator", item["chunk_id"]),
                    "snippet": snippet,
                    **_phase3_local_metadata(item),
                },
                search_text=search_text,
                compact_text=search_text.lower().replace(" ", ""),
                score_bonus=0,
            )

        faq_id = extracted.get("id")
        question = extracted.get("question", "")
        answer = extracted.get("answer", "")
        keywords = extracted.get("keywords", [])
        search_text = " ".join(
            part for part in (question, answer, " ".join(keywords)) if part
        ).strip()
        return _DocumentCandidate(
            item={
                "id": faq_id or item["chunk_id"],
                "answer": answer,
                "source_label": extracted.get("source_label", "HR FAQ"),
                "source_locator": (
                    f"hr_faq_seed_v1#{faq_id}"
                    if faq_id
                    else extracted.get("source_locator")
                    or item.get("source_locator", item["chunk_id"])
                ),
                "snippet": answer[:160],
                **_phase3_local_metadata(item),
            },
            search_text=search_text or answer,
            compact_text=(search_text or answer).lower().replace(" ", ""),
            score_bonus=2,
        )

    @staticmethod
    def _extract_structured_faq(text: str) -> dict[str, Any] | None:
        answer = Retriever._extract_json_field(text, "answer")
        if not answer:
            return None

        faq_id = Retriever._extract_json_field(text, "id")
        question = Retriever._extract_json_field(text, "question") or ""
        source_label = Retriever._extract_json_field(text, "source_label") or "HR FAQ"
        source_locator = Retriever._extract_json_field(text, "source_locator")
        keywords = Retriever._extract_json_array(text, "keywords")
        return {
            "id": faq_id,
            "question": question,
            "answer": answer,
            "keywords": keywords,
            "source_label": source_label,
            "source_locator": source_locator,
        }

    @staticmethod
    def _extract_json_field(text: str, field_name: str) -> str | None:
        pattern = re.compile(
            rf'"{re.escape(field_name)}"\s*:\s*"((?:\\.|[^"\\])*)"',
            re.DOTALL,
        )
        match = pattern.search(text)
        if match is None:
            return None
        return json.loads(f'"{match.group(1)}"')

    @staticmethod
    def _extract_json_array(text: str, field_name: str) -> list[str]:
        pattern = re.compile(
            rf'"{re.escape(field_name)}"\s*:\s*\[(.*?)\]',
            re.DOTALL,
        )
        match = pattern.search(text)
        if match is None:
            return []
        return [
            json.loads(f'"{value}"')
            for value in re.findall(r'"((?:\\.|[^"\\])*)"', match.group(1))
        ]

    def _search_faq(self, tokens: list[str], compact_query: str) -> RetrievalHit | None:
        best_hit: RetrievalHit | None = None
        best_score = 0

        for item in self._faq_repo.list_all():
            if item.get("lifecycle_status", "active") != "active":
                continue

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
            .replace("、", " ")
            .replace("。", " ")
            .replace("！", " ")
            .replace("!", " ")
            .replace("：", " ")
            .replace(":", " ")
        )
        raw_tokens = [token.strip() for token in query.split() if token.strip()]
        if not raw_tokens:
            return []

        tokens = list(raw_tokens)

        for token in raw_tokens:
            has_cjk = any(ord(char) > 127 for char in token)
            if has_cjk and len(token) > 2:
                bigrams = [token[i : i + 2] for i in range(len(token) - 1)]
                for bigram in bigrams:
                    if bigram not in tokens:
                        tokens.append(bigram)
                if len(token) > 4:
                    trigrams = [token[i : i + 3] for i in range(len(token) - 2)]
                    for trigram in trigrams:
                        if trigram not in tokens:
                            tokens.append(trigram)

        return list(dict.fromkeys(tokens))

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


def _phase3_local_metadata(item: dict[str, Any]) -> dict[str, Any]:
    return {
        field: item[field]
        for field in _PHASE3_LOCAL_METADATA_FIELDS
        if field in item
    }
