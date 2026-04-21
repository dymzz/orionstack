"""Planner output-quality contracts from docs/2_6 §5 — LocalRuleProvider edition.

These tests exercise QueryPlanner with ``provider="local"`` and document the
known intrinsic debt of LocalRuleProvider. LocalRule is a deterministic
fallback; as of 2_8 its role changed from primary to last-resort fallback
when the Qwen API path fails. These xfail markers remain because LocalRule's
behavior itself has not changed — they are factually accurate.

Debt-closure status (as of 2_8 轮 3.4 live smoke 2026-04-21):
- **Primary provider (QwenApiProvider) closes all 9 contract debts**, verified by:
  - ``test_planner_qwen_api_contract.py`` (17 mocked ideal-response tests, all green)
  - ``test_planner_qwen_api_live.py`` (19 real DashScope tests, all green; raw
    outputs archived in ``docs/2_8_smoke_live_results__cloud__qwen-plus.json``.
    The file name derives from env at run time so cloud vs local backends
    produce distinct snapshots.)
- LocalRule xfail markers STAY because LocalRule remains the fallback and
  still exhibits these behaviors. Removing them would cause failures the
  moment LocalRule is exercised (e.g., when Qwen raises PlannerHttpError).

Contract test roadmap (LocalRule debt profile, unchanged):
- §5.1 domain_hint          (3 tests, 2 xfail) — always returns None
- §5.2 lexical_terms        (4 tests, 2 xfail) — emits char fragments, no bound
- §5.3 planner_confidence   (2 tests, 2 xfail) — constant 0.88 for any query
- §5.4 normalization        (3 tests, 3 xfail) — only strips outer whitespace
- §5.5 stability            (1 test,  0 xfail) — deterministic by construction

Total: 13 tests, 9 xfail, 4 green. **xfail count here measures LocalRule debt
only**; Qwen primary-path quality is tracked in the two files named above.
See docs/2_7_planner_upgrade_plan.md §3.4 for the original layout rationale
and docs/2_8_smoke_results.md §4 for the formal debt-closure summary.
"""

from __future__ import annotations

import pytest

from app.config.settings import Settings
from app.query.query_planner import QueryPlanner


@pytest.fixture
def planner() -> QueryPlanner:
    return QueryPlanner(provider="local", model="")


# ---------------------------------------------------------------------------
# §5.1 domain_hint contract
# ---------------------------------------------------------------------------


class TestDomainHintContract:
    @pytest.mark.xfail(
        reason="LocalRuleProvider always returns None — see 2_6 §3.1",
        strict=True,
    )
    def test_hr_exclusive_query_gets_hr_hint(self, planner: QueryPlanner) -> None:
        output = planner.plan("请假审批进度在哪里查看？")
        assert output.domain_hint == "hr"

    @pytest.mark.xfail(
        reason="LocalRuleProvider always returns None — see 2_6 §3.1",
        strict=True,
    )
    def test_admin_exclusive_query_gets_admin_hint(
        self, planner: QueryPlanner
    ) -> None:
        output = planner.plan("门禁权限怎么申请？")
        assert output.domain_hint == "admin"

    def test_cross_domain_shared_tokens_get_no_hint(self, planner: QueryPlanner) -> None:
        # "申请" / "提交" are shared across hr / finance / admin / ops —
        # a conservative planner must not narrow. Current stub accidentally
        # satisfies this by returning None unconditionally.
        output = planner.plan("怎么提交申请")
        assert output.domain_hint is None


# ---------------------------------------------------------------------------
# §5.2 lexical_terms contract
# ---------------------------------------------------------------------------


class TestLexicalTermsContract:
    def test_real_tokens_appear(self, planner: QueryPlanner) -> None:
        output = planner.plan("请假审批")
        assert "请假" in output.lexical_terms
        assert "审批" in output.lexical_terms

    @pytest.mark.xfail(
        reason="LocalRuleProvider emits raw character bigram/trigram fragments — see 2_6 §3.2",
        strict=True,
    )
    def test_no_meaningless_character_fragments(self, planner: QueryPlanner) -> None:
        output = planner.plan("请假审批进度")
        # These are character-span fragments with no semantic meaning in Chinese
        # and should be absent from any word-aware lexical extractor.
        assert "假审" not in output.lexical_terms
        assert "批进" not in output.lexical_terms
        assert "假审批" not in output.lexical_terms
        assert "批进度" not in output.lexical_terms

    @pytest.mark.xfail(
        reason="LocalRuleProvider emits O(n) bigrams + O(n) trigrams — see 2_6 §3.2",
        strict=True,
    )
    def test_lexical_terms_bounded_above(self, planner: QueryPlanner) -> None:
        # A single-intent 12-char query should not blow up the lexical_terms
        # list past a sane ceiling; otherwise BM25 signal is diluted.
        output = planner.plan("请假审批进度在哪里可以查看")
        assert len(output.lexical_terms) <= 10

    def test_lexical_terms_deduplicated(self, planner: QueryPlanner) -> None:
        output = planner.plan("请假请假")
        assert len(output.lexical_terms) == len(set(output.lexical_terms))


# ---------------------------------------------------------------------------
# §5.3 planner_confidence contract
# ---------------------------------------------------------------------------


class TestConfidenceContract:
    @pytest.mark.xfail(
        reason="LocalRuleProvider returns 0.88 for any 2+ char query — see 2_6 §3.3",
        strict=True,
    )
    def test_specific_query_higher_confidence_than_pan_query(
        self, planner: QueryPlanner
    ) -> None:
        # A specific, well-formed HR question should read higher confidence
        # than a bare single-token pan query.
        specific = planner.plan("如何申请年假？")
        pan = planner.plan("请假")
        assert specific.planner_confidence > pan.planner_confidence

    @pytest.mark.xfail(
        reason="LocalRuleProvider returns 0.88 for any 2+ char query — see 2_6 §3.3",
        strict=True,
    )
    def test_nonsense_query_low_confidence(self, planner: QueryPlanner) -> None:
        # Random-looking input should fall below the route confidence threshold
        # so that rule_parser fallback engages in _resolve_decision.
        output = planner.plan("xxyyzz乱码输入asdfq")
        assert output.planner_confidence < Settings().route_confidence_threshold


# ---------------------------------------------------------------------------
# §5.4 normalization contract
# ---------------------------------------------------------------------------


class TestNormalizationContract:
    @pytest.mark.xfail(
        reason="LocalRuleProvider only strips outer whitespace — see 2_6 §3.4",
        strict=True,
    )
    def test_fullwidth_punct_normalized(self, planner: QueryPlanner) -> None:
        cjk = planner.plan("请假？")
        ascii_ = planner.plan("请假?")
        assert cjk.normalized_query == ascii_.normalized_query

    @pytest.mark.xfail(
        reason="LocalRuleProvider only strips outer whitespace — see 2_6 §3.4",
        strict=True,
    )
    def test_english_case_normalized(self, planner: QueryPlanner) -> None:
        upper = planner.plan("HR FAQ")
        lower = planner.plan("hr faq")
        assert upper.normalized_query == lower.normalized_query

    @pytest.mark.xfail(
        reason="LocalRuleProvider only strips outer whitespace — see 2_6 §3.4",
        strict=True,
    )
    def test_internal_whitespace_collapsed(self, planner: QueryPlanner) -> None:
        output = planner.plan("请假   审批")
        assert "  " not in output.normalized_query


# ---------------------------------------------------------------------------
# §5.5 stability contract
# ---------------------------------------------------------------------------


class TestStabilityContract:
    def test_determinism_across_repeated_calls(self, planner: QueryPlanner) -> None:
        query = "请假审批进度在哪里查看？"
        outputs = [planner.plan(query) for _ in range(5)]
        first = outputs[0]
        for later in outputs[1:]:
            assert later == first
