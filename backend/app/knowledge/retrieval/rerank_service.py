from __future__ import annotations

import json
import os
import re

from app.integrations.model_gateway import ModelGateway


class RerankService:
    """Re-rank retrieved chunks with a model-first, lexical-fallback strategy."""

    def __init__(
        self,
        *,
        provider: str | None = None,
        model: str | None = None,
    ) -> None:
        self.provider = (provider or os.getenv("ORIONSTACK_RERANK_PROVIDER", "auto")).lower()
        self.model = model or os.getenv("ORIONSTACK_RERANK_MODEL") or os.getenv("ORIONSTACK_OLLAMA_MODEL", "gemma3:1b")
        self.model_gateway = ModelGateway()

    def rerank(self, question: str, candidates: list[dict], top_k: int) -> list[dict]:
        if not candidates:
            return []

        lexical_results = self._lexical_rerank(question=question, candidates=candidates, top_k=len(candidates))
        if self.provider == "lexical":
            return lexical_results[:top_k]

        if self.provider in {"auto", "ollama"}:
            try:
                ranked_chunk_ids = self._rerank_with_ollama(question=question, candidates=lexical_results)
                if ranked_chunk_ids:
                    return self._apply_model_ranking(
                        ranked_chunk_ids=ranked_chunk_ids,
                        candidates=lexical_results,
                        top_k=top_k,
                    )
            except Exception:
                if self.provider == "ollama":
                    raise

        return lexical_results[:top_k]

    def _lexical_rerank(self, question: str, candidates: list[dict], top_k: int) -> list[dict]:
        normalized_question = " ".join(question.lower().split())
        tokens = [token for token in normalized_question.split() if token]

        rescored: list[dict] = []
        for index, candidate in enumerate(candidates):
            snippet = str(candidate.get("snippet", ""))
            normalized_snippet = " ".join(snippet.lower().split())
            lexical_score = self._lexical_score(
                normalized_question=normalized_question,
                normalized_snippet=normalized_snippet,
                tokens=tokens,
            )
            vector_score = float(candidate.get("score", 0.0))
            rerank_score = (vector_score * 0.7) + (lexical_score * 0.3)

            updated = dict(candidate)
            updated["score"] = rerank_score
            updated["vector_score"] = vector_score
            updated["lexical_score"] = lexical_score
            updated["rerank_provider"] = "lexical"
            updated["_original_index"] = index
            rescored.append(updated)

        rescored.sort(
            key=lambda item: (
                item["score"],
                item["lexical_score"],
                item["vector_score"],
                -item["_original_index"],
            ),
            reverse=True,
        )

        final_items = rescored[:top_k]
        for item in final_items:
            item.pop("_original_index", None)
        return final_items

    def _rerank_with_ollama(self, question: str, candidates: list[dict]) -> list[str]:
        candidate_lines = []
        for candidate in candidates:
            candidate_lines.append(
                json.dumps(
                    {
                        "chunk_id": candidate.get("chunk_id"),
                        "document_name": candidate.get("document_name"),
                        "snippet": candidate.get("snippet"),
                    },
                    ensure_ascii=False,
                )
            )

        prompt = (
            "You are a retrieval reranker.\n"
            "Given a question and candidate snippets, rank the chunk_ids from most relevant to least relevant.\n"
            "Return JSON only in this format: {\"ranked_chunk_ids\": [\"id1\", \"id2\"]}\n\n"
            f"Question:\n{question}\n\n"
            "Candidates:\n"
            + "\n".join(candidate_lines)
        )

        content = self.model_gateway.generate(
            provider="ollama",
            model=self.model,
            prompt=prompt,
            response_format={
                "type": "object",
                "properties": {
                    "ranked_chunk_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                    }
                },
                "required": ["ranked_chunk_ids"],
            },
            timeout=30.0,
        )
        return self._extract_ranked_chunk_ids(content)

    def _extract_ranked_chunk_ids(self, content: str) -> list[str]:
        if not content:
            return []

        parsed = self._try_parse_json(content)
        if parsed:
            return parsed

        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            parsed = self._try_parse_json(match.group(0))
            if parsed:
                return parsed

        bracket_match = re.search(r"\[[^\]]*\]", content, re.DOTALL)
        if bracket_match:
            try:
                raw = json.loads(bracket_match.group(0))
                if isinstance(raw, list):
                    return [str(item) for item in raw if str(item).strip()]
            except json.JSONDecodeError:
                return []

        return []

    def _try_parse_json(self, content: str) -> list[str]:
        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            return []

        if isinstance(payload, dict):
            raw = payload.get("ranked_chunk_ids", [])
            if isinstance(raw, list):
                return [str(item) for item in raw if str(item).strip()]
        return []

    def _apply_model_ranking(
        self,
        *,
        ranked_chunk_ids: list[str],
        candidates: list[dict],
        top_k: int,
    ) -> list[dict]:
        by_chunk_id = {str(item.get("chunk_id", "")): dict(item) for item in candidates}
        ordered: list[dict] = []
        seen: set[str] = set()

        total = max(len(candidates), 1)
        for position, chunk_id in enumerate(ranked_chunk_ids):
            if chunk_id in seen or chunk_id not in by_chunk_id:
                continue
            item = by_chunk_id[chunk_id]
            item["model_rank"] = position + 1
            item["rerank_provider"] = "ollama"
            item["score"] = max(float(item.get("score", 0.0)), 0.0) + ((total - position) / total)
            ordered.append(item)
            seen.add(chunk_id)

        for candidate in candidates:
            chunk_id = str(candidate.get("chunk_id", ""))
            if chunk_id in seen:
                continue
            item = dict(candidate)
            item["rerank_provider"] = "lexical-fallback"
            ordered.append(item)

        return ordered[:top_k]

    def _lexical_score(
        self,
        *,
        normalized_question: str,
        normalized_snippet: str,
        tokens: list[str],
    ) -> float:
        if not normalized_snippet:
            return 0.0

        token_hits = 0.0
        for token in tokens:
            if token in normalized_snippet:
                token_hits += 1.0 + (normalized_snippet.count(token) * 0.1)

        phrase_bonus = 0.0
        if normalized_question and normalized_question in normalized_snippet:
            phrase_bonus += 2.0

        ordered_bonus = 0.0
        if len(tokens) >= 2:
            for left, right in zip(tokens, tokens[1:], strict=False):
                pair = f"{left} {right}"
                if pair in normalized_snippet:
                    ordered_bonus += 0.4

        coverage_bonus = (token_hits / len(tokens)) if tokens else 0.0
        return token_hits + phrase_bonus + ordered_bonus + coverage_bonus
