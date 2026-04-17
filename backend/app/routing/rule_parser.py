import re

from app.routing.contracts import IntentDecision


class RuleParser:
    _NON_FAQ_INPUTS = {"hi", "hello", "你好", "您好", "测试"}

    def parse(self, raw_query: str) -> IntentDecision:
        normalized = re.sub(r"\s+", " ", raw_query).strip().lower()
        if not normalized:
            return IntentDecision(route="fallback", confidence=0.0, query_for_search="")

        if normalized in self._NON_FAQ_INPUTS:
            return IntentDecision(
                route="fallback", confidence=0.2, query_for_search=normalized
            )

        confidence = 0.45
        if len(normalized) >= 2:
            confidence += 0.15
        if len(normalized) >= 6:
            confidence += 0.15
        if len(normalized) > 80:
            confidence -= 0.15

        confidence = max(0.0, min(confidence, 1.0))
        route = "faq_qa" if confidence >= 0.15 else "fallback"
        return IntentDecision(
            route=route, confidence=confidence, query_for_search=normalized
        )
