import re

from app.routing.contracts import IntentDecision


class RuleParser:
    _FAQ_HINTS = (
        "faq",
        "文档",
        "知识",
        "引用",
        "来源",
        "定位",
        "上传",
        "检索",
        "索引",
        "demo",
        "模式",
        "mock",
        "trace",
        "healthz",
        "接口",
    )
    _QUESTION_HINTS = (
        "如何",
        "怎么",
        "怎样",
        "查看",
        "进入",
        "是否",
        "什么",
        "哪里",
        "可以",
        "?",
        "？",
    )
    _NON_FAQ_INPUTS = {"hi", "hello", "你好", "您好", "测试"}

    def parse(self, raw_query: str) -> IntentDecision:
        normalized = re.sub(r"\s+", " ", raw_query).strip().lower()
        if not normalized:
            return IntentDecision(route="fallback", confidence=0.0, query_for_search="")

        if normalized in self._NON_FAQ_INPUTS:
            return IntentDecision(route="fallback", confidence=0.2, query_for_search=normalized)

        confidence = 0.0
        if any(term in normalized for term in self._FAQ_HINTS):
            confidence += 0.45
        if any(term in normalized for term in self._QUESTION_HINTS):
            confidence += 0.35
        if len(normalized) >= 6 and any(term in normalized for term in self._QUESTION_HINTS):
            confidence += 0.15
        if len(normalized) >= 2:
            confidence += 0.15
        if len(normalized) > 80:
            confidence -= 0.15

        confidence = max(0.0, min(confidence, 1.0))
        route = "faq_qa" if confidence >= 0.45 else "fallback"
        return IntentDecision(route=route, confidence=confidence, query_for_search=normalized)
