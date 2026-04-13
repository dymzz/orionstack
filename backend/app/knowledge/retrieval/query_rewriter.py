from __future__ import annotations

import json
import re
from typing import Any

from app.integrations.model_gateway import ModelGateway


class QueryRewriter:
    """Lightweight local-LLM query rewrite for short, underspecified questions."""

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

    def rewrite(self, question: str) -> str:
        normalized = " ".join(str(question).split()).strip()
        if not self._should_rewrite(normalized):
            return normalized

        rule_based = self._rewrite_rule_based(normalized)
        if rule_based:
            return rule_based

        try:
            content = self.model_gateway.generate(
                provider=self.provider,
                model=self.model,
                prompt=self._build_prompt(normalized),
                response_format={
                    "type": "object",
                    "properties": {
                        "queries": {
                            "type": "array",
                            "items": {"type": "string"},
                        }
                    },
                    "required": ["queries"],
                },
                timeout=12.0,
            )
            queries = self._parse_queries(content)
            if queries:
                return " ".join(queries[:3])
        except Exception:
            pass
        return normalized

    def _should_rewrite(self, question: str) -> bool:
        if not question:
            return False
        compact = re.sub(r"\s+", "", question)
        if len(compact) <= 6:
            return True
        return any(token in compact for token in ["怎么", "如何", "怎样", "咋", "怎么办"])

    def _rewrite_rule_based(self, question: str) -> str:
        compact = re.sub(r"\s+", "", question)
        if not compact:
            return ""

        candidate = compact
        for prefix in ["请问一下", "请问", "麻烦问下", "麻烦问一下", "我想问一下", "想问一下", "帮我看下", "帮我看看"]:
            if candidate.startswith(prefix):
                candidate = candidate[len(prefix):]

        candidate = re.sub(r"^(如何|怎么|怎样|咋|怎么办)", "", candidate)
        candidate = re.sub(r"(在哪里看|在哪看)$", "", candidate)
        candidate = re.sub(r"(如何申请|怎么申请|怎样申请)$", "申请", candidate)
        candidate = re.sub(r"(如何预订|怎么预订|怎样预订)$", "预订", candidate)
        candidate = re.sub(r"(多久到账)$", "到账", candidate)
        candidate = candidate.strip("：:，,。.!！？? ")

        if not candidate:
            return compact
        return candidate

    def _build_prompt(self, question: str) -> str:
        return (
            "你是企业知识库检索查询改写器。\n"
            "你的任务是把用户的简短问句，改写成更利于检索的短查询。\n"
            "规则：\n"
            "1. 保持原问题主题不变。\n"
            "2. 不要扩展到相邻事项或别的制度。\n"
            "3. 如果用户问题较泛，可以补充同一主题下常见的正式表达或子类型。\n"
            "4. 输出 1 到 3 条简短查询，适合检索，不要写解释。\n"
            "5. 仅返回 JSON：{\"queries\": [\"...\", \"...\"]}\n\n"
            f"用户问题：{question}"
        )

    def _parse_queries(self, content: str) -> list[str]:
        raw = str(content).strip()
        if not raw:
            return []
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if not match:
                return []
            payload = json.loads(match.group(0))

        if not isinstance(payload, dict):
            return []
        queries = payload.get("queries", [])
        if not isinstance(queries, list):
            return []

        seen: set[str] = set()
        results: list[str] = []
        for item in queries:
            text = " ".join(str(item).split()).strip()
            if not text or text in seen:
                continue
            seen.add(text)
            results.append(text)
        return results
