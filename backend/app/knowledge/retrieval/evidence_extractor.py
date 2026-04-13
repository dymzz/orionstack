from __future__ import annotations

import json
import re
from typing import Any

from app.integrations.model_gateway import ModelGateway
from app.knowledge.retrieval.query_tokenizer import build_query_features, build_text_features, lexical_score


class EvidenceExtractor:
    """Filter retrieved citations down to directly answerable evidence."""

    def __init__(
        self,
        *,
        model_gateway: ModelGateway | None = None,
        provider: str = "ollama",
        model: str = "gemma3:1b",
    ) -> None:
        self.model_gateway = model_gateway or ModelGateway()
        self.provider = provider
        self.model = model

    def extract(self, *, question: str, citations: list[dict]) -> dict[str, Any]:
        if not citations:
            return {
                "citations": [],
                "facts": [],
                "confidence": 0.0,
                "reason": "no_citations",
                "provider": "none",
            }

        try:
            extracted = self._extract_with_model(question=question, citations=citations)
            return extracted
        except Exception:
            pass

        return self._extract_with_lexical_fallback(question=question, citations=citations)

    def _extract_with_model(self, *, question: str, citations: list[dict]) -> dict[str, Any]:
        response = self.model_gateway.generate(
            provider=self.provider,
            model=self.model,
            prompt=self._build_prompt(question=question, citations=citations),
            response_format={
                "type": "object",
                "properties": {
                    "relevant_chunk_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "facts": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "confidence": {"type": "number"},
                    "reason": {"type": "string"},
                },
                "required": ["relevant_chunk_ids", "facts", "confidence"],
            },
            timeout=20.0,
        )
        payload = self._parse_json_payload(response)
        return self._normalize_payload(payload=payload, citations=citations, provider="ollama_filter")

    def _extract_with_lexical_fallback(self, *, question: str, citations: list[dict]) -> dict[str, Any]:
        query_features = build_query_features(question)
        scored: list[tuple[float, dict]] = []
        for citation in citations:
            candidate_text = " ".join(
                [
                    str(citation.get("document_name", "")),
                    str(citation.get("content", "")) or str(citation.get("snippet", "")),
                ]
            ).lower()
            score = lexical_score(
                query=query_features,
                candidate=build_text_features(candidate_text),
            )
            if score > 0:
                scored.append((score, citation))

        if not scored:
            return {
                "citations": [],
                "facts": [],
                "confidence": 0.0,
                "reason": "lexical_no_match",
                "provider": "lexical_filter",
            }

        scored.sort(key=lambda item: item[0], reverse=True)
        kept = [dict(item[1]) for item in scored[: min(2, len(scored))]]
        top_score = scored[0][0]
        confidence = min(0.75, 0.35 + (top_score / max(len(query_features.terms), 1)) * 0.2)
        facts = [str(item.get("snippet", "")).strip() for item in kept if str(item.get("snippet", "")).strip()]
        return {
            "citations": kept,
            "facts": facts[:3],
            "confidence": confidence,
            "reason": "lexical_match",
            "provider": "lexical_filter",
        }

    def _build_prompt(self, *, question: str, citations: list[dict]) -> str:
        evidence_lines = []
        for index, citation in enumerate(citations, start=1):
            evidence_lines.append(
                (
                    f"{index}. chunk_id={citation.get('chunk_id', '')}; "
                    f"document={citation.get('document_name', '')}; "
                    f"content={citation.get('content', '') or citation.get('snippet', '')}"
                )
            )
        return (
            "你是企业知识问答中的证据抽取器。\n"
            "你的任务不是生成最终答案，而是从候选片段中筛出能直接回答问题的证据。\n"
            "严格规则：\n"
            "1. 只保留与问题直接相关的片段。\n"
            "2. 忽略相邻事项、相邻制度、扩展说明、行政FAQ、顺手提到的别的流程。\n"
            "3. 如果片段只是背景信息、相关但未被直接问到，也不要保留。\n"
            "4. facts 只写可直接支持回答的短句，不要自由发挥。\n"
            "5. 如果没有直接证据，返回空 relevant_chunk_ids，并将 confidence 设得很低。\n"
            "仅返回 JSON。\n\n"
            f"问题：\n{question}\n\n"
            f"候选片段：\n" + "\n".join(evidence_lines)
        )

    def _normalize_payload(self, *, payload: dict[str, Any], citations: list[dict], provider: str) -> dict[str, Any]:
        citations_by_chunk_id = {
            str(citation.get("chunk_id", "")): dict(citation)
            for citation in citations
            if str(citation.get("chunk_id", "")).strip()
        }
        relevant_chunk_ids = payload.get("relevant_chunk_ids", [])
        kept: list[dict] = []
        if isinstance(relevant_chunk_ids, list):
            seen: set[str] = set()
            for chunk_id in relevant_chunk_ids:
                normalized_chunk_id = str(chunk_id).strip()
                if not normalized_chunk_id or normalized_chunk_id in seen:
                    continue
                citation = citations_by_chunk_id.get(normalized_chunk_id)
                if citation is not None:
                    kept.append(citation)
                    seen.add(normalized_chunk_id)

        facts_payload = payload.get("facts", [])
        facts = []
        if isinstance(facts_payload, list):
            for item in facts_payload:
                text = str(item).strip()
                if text:
                    facts.append(text)

        confidence_raw = payload.get("confidence", 0.0)
        try:
            confidence = float(confidence_raw)
        except (TypeError, ValueError):
            confidence = 0.0
        confidence = max(0.0, min(confidence, 1.0))

        return {
            "citations": kept,
            "facts": facts[:3],
            "confidence": confidence,
            "reason": str(payload.get("reason", "")).strip(),
            "provider": provider,
        }

    def _parse_json_payload(self, content: str) -> dict[str, Any]:
        raw = content.strip()
        if not raw:
            raise ValueError("empty extractor payload")
        try:
            payload = json.loads(raw)
            if isinstance(payload, dict):
                return payload
        except json.JSONDecodeError:
            pass

        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            raise ValueError("extractor payload is not valid JSON")
        payload = json.loads(match.group(0))
        if not isinstance(payload, dict):
            raise ValueError("extractor payload is not a JSON object")
        return payload
