"""Contract mirror: verify QwenApiProvider parse pipeline maps IDEAL LLM
responses to PlannerOutputs that satisfy the 5 contract groups from
docs/2_6_planner_quality_review.md §5.

Scope (docs/2_8_planner_llm_integration.md §7.2):
- This file does NOT test the LLM itself. It tests that IF the LLM produces
  the ideal structured response for a given input, the parser produces a
  PlannerOutput that satisfies the corresponding contract.
- The ideal responses here serve as a specification for 3.4 smoke evaluation:
  when running against real DashScope, outputs that match these shapes will
  pass their corresponding contracts.

Contract groups (mirrored from test_planner_contract.py):
- §5.1 domain_hint       — narrow only on domain-exclusive tokens
- §5.2 lexical_terms     — real words, bounded, deduplicated
- §5.3 confidence        — specific > pan, nonsense low
- §5.4 normalization     — fullwidth/case/whitespace collapsed
- §5.5 stability         — out of scope here (LLM determinism is provider
                           concern, not parser concern; covered by temp=0 +
                           cache contract)
"""

from __future__ import annotations

import json

import httpx
import pytest

from app.query.providers import QwenApiProvider


_DOMAIN_ENUM = ("hr", "finance", "admin", "it", "ops", "legal", "product", "sales")


def _make_provider_returning(payload: dict) -> QwenApiProvider:
    envelope = {"choices": [{"message": {"content": json.dumps(payload)}}]}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=envelope)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    return QwenApiProvider(
        api_base="http://mock",
        api_model="qwen-test",
        api_key="mock-key",
        timeout_seconds=1.0,
        http_client=client,
    )


# ---------------------------------------------------------------------------
# §5.1 domain_hint contract
# ---------------------------------------------------------------------------


class TestDomainHintContractMirror:
    def test_hr_exclusive_query_ideal_response(self) -> None:
        # Ideal LLM response for "请假审批进度在哪里查看？"
        ideal = {
            "normalized_query": "请假审批进度在哪里查看?",
            "domain_hint": "hr",
            "lexical_terms": ["请假审批", "审批进度", "请假"],
            "planner_confidence": 0.88,
        }
        provider = _make_provider_returning(ideal)
        output = provider.plan("请假审批进度在哪里查看？")
        assert output.domain_hint == "hr"

    def test_admin_exclusive_query_ideal_response(self) -> None:
        ideal = {
            "normalized_query": "门禁权限怎么申请?",
            "domain_hint": "admin",
            "lexical_terms": ["门禁权限", "门禁", "申请"],
            "planner_confidence": 0.85,
        }
        provider = _make_provider_returning(ideal)
        output = provider.plan("门禁权限怎么申请？")
        assert output.domain_hint == "admin"

    def test_cross_domain_shared_tokens_null_hint(self) -> None:
        # "申请" / "提交" are shared across 4+ domains — ideal response is null
        ideal = {
            "normalized_query": "怎么提交申请",
            "domain_hint": None,
            "lexical_terms": ["提交申请", "申请"],
            "planner_confidence": 0.35,
        }
        provider = _make_provider_returning(ideal)
        output = provider.plan("怎么提交申请")
        assert output.domain_hint is None


# ---------------------------------------------------------------------------
# §5.2 lexical_terms contract
# ---------------------------------------------------------------------------


class TestLexicalTermsContractMirror:
    def test_real_tokens_only_no_character_fragments(self) -> None:
        # Contract: no meaningless fragments like "假审" / "批进"
        ideal = {
            "normalized_query": "请假审批进度",
            "domain_hint": "hr",
            "lexical_terms": ["请假审批", "审批进度", "请假", "审批"],
            "planner_confidence": 0.80,
        }
        provider = _make_provider_returning(ideal)
        output = provider.plan("请假审批进度")
        for forbidden in ("假审", "批进", "假审批", "批进度"):
            assert forbidden not in output.lexical_terms

    def test_lexical_terms_bounded_at_ten(self) -> None:
        # Even if LLM over-produces, parser must truncate
        ideal = {
            "normalized_query": "请假审批进度在哪里可以查看",
            "domain_hint": "hr",
            "lexical_terms": [f"term_{i}" for i in range(25)],
            "planner_confidence": 0.7,
        }
        provider = _make_provider_returning(ideal)
        output = provider.plan("请假审批进度在哪里可以查看")
        assert len(output.lexical_terms) <= 10

    def test_lexical_terms_deduplicated(self) -> None:
        ideal = {
            "normalized_query": "请假请假",
            "domain_hint": "hr",
            "lexical_terms": ["请假", "请假", "假请"],
            "planner_confidence": 0.4,
        }
        provider = _make_provider_returning(ideal)
        output = provider.plan("请假请假")
        assert len(output.lexical_terms) == len(set(output.lexical_terms))


# ---------------------------------------------------------------------------
# §5.3 planner_confidence contract
# ---------------------------------------------------------------------------


class TestConfidenceContractMirror:
    def test_specific_query_high_confidence(self) -> None:
        ideal = {
            "normalized_query": "如何申请年假?",
            "domain_hint": "hr",
            "lexical_terms": ["申请年假", "年假"],
            "planner_confidence": 0.92,
        }
        provider = _make_provider_returning(ideal)
        output = provider.plan("如何申请年假？")
        assert output.planner_confidence >= 0.80

    def test_pan_query_moderate_confidence(self) -> None:
        ideal = {
            "normalized_query": "请假",
            "domain_hint": "hr",
            "lexical_terms": ["请假"],
            "planner_confidence": 0.38,
        }
        provider = _make_provider_returning(ideal)
        output = provider.plan("请假")
        # Pan queries should be in the "ambiguous" range
        assert 0.20 <= output.planner_confidence <= 0.60

    def test_nonsense_query_low_confidence(self) -> None:
        from app.config.settings import Settings

        ideal = {
            "normalized_query": "xxyyzz 乱码输入 asdfq",
            "domain_hint": None,
            "lexical_terms": ["乱码输入"],
            "planner_confidence": 0.08,
        }
        provider = _make_provider_returning(ideal)
        output = provider.plan("xxyyzz乱码输入asdfq")
        # Must fall below the route_confidence_threshold so rule_parser fallback
        # engages in _resolve_decision
        assert output.planner_confidence < Settings().route_confidence_threshold


# ---------------------------------------------------------------------------
# §5.4 normalization contract
# ---------------------------------------------------------------------------


class TestNormalizationContractMirror:
    @pytest.mark.parametrize(
        "raw_input,normalized",
        [
            ("请假？", "请假?"),  # fullwidth punct → ASCII
            ("HR FAQ", "hr faq"),  # case lowered
            ("请假   审批", "请假 审批"),  # whitespace collapsed
        ],
    )
    def test_normalization_ideal_response(self, raw_input: str, normalized: str) -> None:
        ideal = {
            "normalized_query": normalized,
            "domain_hint": None,
            "lexical_terms": [normalized],
            "planner_confidence": 0.5,
        }
        provider = _make_provider_returning(ideal)
        output = provider.plan(raw_input)
        assert output.normalized_query == normalized


# ---------------------------------------------------------------------------
# Schema enum coverage — parser accepts all domain values
# ---------------------------------------------------------------------------


class TestDomainEnumCoverage:
    @pytest.mark.parametrize("domain", _DOMAIN_ENUM)
    def test_all_domains_roundtrip(self, domain: str) -> None:
        ideal = {
            "normalized_query": "x",
            "domain_hint": domain,
            "lexical_terms": ["x"],
            "planner_confidence": 0.7,
        }
        provider = _make_provider_returning(ideal)
        output = provider.plan("x")
        assert output.domain_hint == domain
