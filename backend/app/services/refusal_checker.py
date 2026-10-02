from __future__ import annotations

_REFUSAL_TERMS = {
    "unsafe_request": (
        "炸弹",
        "爆炸物",
        "攻击系统",
        "木马",
        "勒索",
        "窃取密码",
        "毒品",
        "伪造证件",
        "自杀",
    ),
}


def match_refusal_reason(normalized_query: str) -> str | None:
    lowered_query = normalized_query.lower()
    for reason, terms in _REFUSAL_TERMS.items():
        if any(term in lowered_query for term in terms):
            return reason
    return None