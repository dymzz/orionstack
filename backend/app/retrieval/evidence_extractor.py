from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class EvidenceSpan:
    text: str
    start: int
    end: int


@dataclass(frozen=True)
class EvidenceResult:
    evidence_spans: list[EvidenceSpan]
    evidence_confidence: float


class EvidenceExtractor:
    def extract(self, query: str, text: str) -> EvidenceResult:
        if not query.strip() or not text.strip():
            return EvidenceResult(evidence_spans=[], evidence_confidence=0.0)

        query_terms = _extract_query_terms(query)
        if not query_terms:
            return EvidenceResult(evidence_spans=[], evidence_confidence=0.0)

        sentence_hits: list[tuple[float, EvidenceSpan]] = []
        for sentence, start, end in _split_sentences(text):
            overlap = [term for term in query_terms if term in sentence]
            if not overlap:
                continue
            confidence = len(overlap) / len(query_terms)
            sentence_hits.append(
                (
                    confidence,
                    EvidenceSpan(text=sentence, start=start, end=end),
                )
            )

        sentence_hits.sort(key=lambda item: item[0], reverse=True)
        spans = [span for _, span in sentence_hits[:2]]
        confidence = 0.0 if not sentence_hits else sentence_hits[0][0]
        return EvidenceResult(evidence_spans=spans, evidence_confidence=confidence)


def _split_sentences(text: str) -> list[tuple[str, int, int]]:
    matches = list(re.finditer(r"[^。！？；\n]+", text))
    if not matches:
        compact = text.strip()
        return [] if not compact else [(compact, 0, len(compact))]

    sentences: list[tuple[str, int, int]] = []
    for match in matches:
        sentence = match.group(0).strip()
        if sentence:
            sentences.append((sentence, match.start(), match.end()))
    return sentences


def _extract_query_terms(query: str) -> list[str]:
    terms: list[str] = []
    normalized = " ".join(query.split())
    for part in normalized.split(" "):
        if part and part not in terms:
            terms.append(part)

    compact = normalized.replace(" ", "")
    if compact and compact not in terms:
        terms.append(compact)
    if len(compact) > 1:
        for index in range(len(compact) - 1):
            token = compact[index : index + 2]
            if token not in terms:
                terms.append(token)
    return terms
