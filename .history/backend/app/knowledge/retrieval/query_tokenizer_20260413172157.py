from __future__ import annotations

import re
from dataclasses import dataclass

from app.knowledge.retrieval.query_rewrite_lexicon import (
    GENERIC_FUNCTION_TERMS,
    QUESTION_PREFIXES,
    QUESTION_SUFFIXES,
)


_CJK_SPAN_RE = re.compile(r"[\u4e00-\u9fff]+")
_LATIN_TERM_RE = re.compile(r"[a-z0-9][a-z0-9._-]*")
_COMPACT_RE = re.compile(r"[\u4e00-\u9fffA-Za-z0-9._-]+")


@dataclass(slots=True)
class QueryLexicalFeatures:
    normalized: str
    compact: str
    terms: list[str]


@dataclass(slots=True)
class TextLexicalFeatures:
    normalized: str
    compact: str


def build_query_features(text: str) -> QueryLexicalFeatures:
    original_normalized = normalize_text(text)
    normalized = _strip_query_shell(original_normalized) or original_normalized
    compact = compact_text(normalized)
    return QueryLexicalFeatures(
        normalized=normalized,
        compact=compact,
        terms=_extract_search_terms(normalized),
    )


def build_text_features(text: str) -> TextLexicalFeatures:
    return TextLexicalFeatures(
        normalized=normalize_text(text),
        compact=compact_text(text),
    )


def normalize_text(text: str) -> str:
    return " ".join(str(text).lower().split())


def compact_text(text: str) -> str:
    return "".join(_COMPACT_RE.findall(str(text).lower()))


def lexical_score(
    *,
    query: QueryLexicalFeatures,
    candidate: TextLexicalFeatures,
) -> float:
    if not candidate.normalized:
        return 0.0

    token_score = 0.0
    matched_terms = 0
    for term in query.terms:
        haystack = candidate.compact if _is_cjk_term(term) else candidate.normalized
        occurrences = haystack.count(term)
        if occurrences <= 0:
            continue
        matched_terms += 1
        token_score += _term_weight(term) + ((occurrences - 1) * 0.1)

    phrase_bonus = 0.0
    if query.compact and len(query.compact) >= 2 and query.compact in candidate.compact:
        phrase_bonus += 2.0
    elif (
        query.normalized
        and len(query.normalized) >= 2
        and query.normalized in candidate.normalized
    ):
        phrase_bonus += 1.5

    coverage_bonus = (matched_terms / len(query.terms)) if query.terms else 0.0
    return token_score + phrase_bonus + coverage_bonus


def _strip_query_shell(normalized: str) -> str:
    text = normalized.strip()
    if not text:
        return text

    changed = True
    while changed and text:
        changed = False

        for prefix in sorted(QUESTION_PREFIXES, key=len, reverse=True):
            if text.startswith(prefix):
                text = text[len(prefix) :].strip()
                changed = True
                break

        for suffix in sorted(QUESTION_SUFFIXES, key=len, reverse=True):
            if text.endswith(suffix):
                text = text[: -len(suffix)].strip()
                changed = True
                break

        while text.endswith(("吗", "呢", "呀", "啊", "吧", "？", "?")):
            text = text[:-1].strip()
            changed = True

    return text


def _extract_search_terms(normalized: str) -> list[str]:
    terms: list[str] = []

    for token in _LATIN_TERM_RE.findall(normalized):
        if len(token) >= 2 and token not in GENERIC_FUNCTION_TERMS:
            terms.append(token)

    for span in _CJK_SPAN_RE.findall(normalized):
        span = span.strip()
        if not span:
            continue
        terms.extend(_cjk_ngrams(span))

    seen: set[str] = set()
    unique_terms: list[str] = []
    for term in terms:
        if not term or term in seen or term in GENERIC_FUNCTION_TERMS:
            continue
        unique_terms.append(term)
        seen.add(term)
    return unique_terms


def _cjk_ngrams(span: str) -> list[str]:
    terms: list[str] = []
    max_n = min(3, len(span))
    for n in range(max_n, 1, -1):
        for start in range(0, len(span) - n + 1):
            terms.append(span[start : start + n])
    if len(span) <= 3:
        terms.append(span)
    return terms


def _is_cjk_term(term: str) -> bool:
    return bool(term) and all("\u4e00" <= char <= "\u9fff" for char in term)


def _term_weight(term: str) -> float:
    if _is_cjk_term(term):
        if len(term) >= 3:
            return 1.35
        if len(term) == 2:
            return 1.15
        return 1.0
    if len(term) >= 6:
        return 1.25
    return 1.0
