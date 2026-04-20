import pytest

from app.config.settings import Settings
from app.query.query_planner import PlannerOutput
from app.schemas.request import ChatAskRequest
from app.services import chat_service as chat_service_module
from app.services.chat_service import ChatService
from conftest import load_seed_faqs
from test_phase2_retrieval import (
    _FakeHybridRetriever,
    _FakeLexicalRetriever,
    _FakePlanner,
    _build_fixture_hybrid_hit,
    _build_fixture_lexical_hit,
    _build_local_planner_output,
)


def _seed_by_id(faq_id: str) -> dict:
    for item in load_seed_faqs():
        if item["id"] == faq_id:
            return item
    raise KeyError(faq_id)


def _install_fakes(monkeypatch, *, lexical, hybrid, planner) -> None:
    monkeypatch.setattr(
        chat_service_module,
        "settings",
        Settings(
            search_backend="elasticsearch",
            elastic_url="http://localhost:9200",
            enable_query_planner=True,
            enable_fast_track=True,
        ),
    )
    monkeypatch.setattr(
        ChatService, "_create_lexical_retriever", lambda self: lexical
    )
    monkeypatch.setattr(
        ChatService, "_create_hybrid_retriever", lambda self: hybrid
    )
    monkeypatch.setattr(
        ChatService, "_create_query_planner", lambda self: planner
    )


@pytest.mark.parametrize(
    "faq_id, raw_query",
    [
        ("admin-faq-001", "会议室怎么预订？"),
        ("finance-faq-001", "如何提交日常报销？"),
        ("it-faq-001", "忘记登录密码怎么办？"),
        ("ops-faq-001", "服务告警在哪里查看？"),
    ],
)
def test_chat_service_answers_typical_query_for_non_hr_domain_seed(
    monkeypatch,
    faq_id: str,
    raw_query: str,
) -> None:
    # Domain coverage smoke: admin / finance / it / ops domain seeds are
    # loaded by conftest.load_seed_faqs() but no prior test exercised the
    # full ChatService pipeline on any of them — only HR was covered via
    # fixture_case(). This binds each non-HR domain seed to a baseline
    # regression so future seed edits or retrieval refactors that break a
    # single domain are caught, not just HR.
    item = _seed_by_id(faq_id)

    fake_lexical = _FakeLexicalRetriever(
        [_build_fixture_lexical_hit(item, score=2.5)]
    )
    fake_hybrid = _FakeHybridRetriever(
        [
            _build_fixture_hybrid_hit(
                item,
                score=0.033,
                lexical_rank=1,
                vector_rank=1,
                rrf_rank=1,
                bm25_score=2.5,
                vector_score=0.9,
            )
        ]
    )
    fake_planner = _FakePlanner(_build_local_planner_output(raw_query))

    _install_fakes(
        monkeypatch, lexical=fake_lexical, hybrid=fake_hybrid, planner=fake_planner
    )

    service = ChatService()
    response = service.ask(
        ChatAskRequest(raw_query=raw_query, debug=True),
        trace_id=f"trace-phase2-cross-domain-smoke-{faq_id}",
        debug_enabled=True,
    )

    assert response.response_status == "ok"
    assert response.clarification is None
    assert len(response.citations) == 1
    assert response.citations[0].citation_id == faq_id
    assert response.citations[0].source_locator == item["source_locator"]
    assert response.debug_info is not None
    assert response.debug_info.rerank_accept is True
    assert response.debug_info.retrieved_chunks == [faq_id]


def test_chat_service_picks_hr_leave_progress_over_finance_payment_progress_on_shared_structural_keywords(
    monkeypatch,
) -> None:
    # 2_4 §9.4 cross-domain contamination: the HR FAQ
    #   hr-faq-003 "请假审批进度在哪里查看？"
    # and the finance FAQ
    #   finance-faq-004 "付款申请提交后在哪里查看进度？"
    # share most non-domain tokens (申请 / 提交 / 在哪里 / 查看 / 进度 /
    # 审批记录) and have structurally parallel answers. This is exactly
    # the kind of pair that slips past naive lexical matching once the
    # planner cannot infer domain_hint and business_domain narrow no
    # longer applies.
    #
    # Scenario: fake the fusion layer so the finance contaminant sits at
    # rank 1 above the correct HR answer. The rerank layer must still
    # pick HR because evidence_confidence of the HR item against the HR
    # query is far higher than the finance item's. This exercises the
    # defence-in-depth property of §2 in 2_5_retrieval_defense_discipline
    # — when narrow fails, rerank/evidence picks up the slack.
    hr_item = _seed_by_id("hr-faq-003")
    finance_item = _seed_by_id("finance-faq-004")

    fake_lexical = _FakeLexicalRetriever(
        [_build_fixture_lexical_hit(hr_item, score=2.3)]
    )
    fake_hybrid = _FakeHybridRetriever(
        [
            _build_fixture_hybrid_hit(
                finance_item,
                score=0.033,
                lexical_rank=1,
                vector_rank=1,
                rrf_rank=1,
                bm25_score=2.5,
                vector_score=0.87,
            ),
            _build_fixture_hybrid_hit(
                hr_item,
                score=0.031,
                lexical_rank=2,
                vector_rank=2,
                rrf_rank=2,
                bm25_score=2.4,
                vector_score=0.85,
            ),
        ]
    )
    fake_planner = _FakePlanner(
        PlannerOutput(
            normalized_query="请假审批进度在哪里查看？",
            domain_hint=None,
            lexical_terms=["请假", "审批", "进度", "查看"],
            planner_confidence=0.85,
        )
    )

    _install_fakes(
        monkeypatch, lexical=fake_lexical, hybrid=fake_hybrid, planner=fake_planner
    )

    service = ChatService()
    response = service.ask(
        ChatAskRequest(raw_query="请假审批进度在哪里查看？", debug=True),
        trace_id="trace-phase2-cross-domain-progress",
        debug_enabled=True,
    )

    assert response.response_status == "ok"
    assert len(response.citations) == 1
    assert response.citations[0].citation_id == "hr-faq-003"
    assert response.citations[0].source_locator == hr_item["source_locator"]
    assert response.debug_info is not None
    assert response.debug_info.rerank_accept is True
    # Explicit reverse guard: the finance contaminant that won fusion
    # must not appear as the user-facing answer.
    assert response.debug_info.retrieved_chunks == ["hr-faq-003"]
    assert "finance-faq-004" not in [c.citation_id for c in response.citations]


# ---------------------------------------------------------------------------
# Admin × IT 权限 symmetric contamination pair
#
#   admin-faq-003 "门禁权限怎么申请？"
#   it-faq-012    "如何申请系统权限开通？"
#
# Both FAQs share the pattern "X 权限怎么申请" in the question and
# "如需开通...权限，可通过...入口提交申请...审批" in the answer. A user
# query like "权限怎么申请" is genuinely ambiguous and will surface both
# candidates. These two tests pin down that when one domain's FAQ is the
# true answer, a rank-1 fusion contaminant from the other domain must
# not leak into the user-visible citation — in both directions.
# ---------------------------------------------------------------------------


def test_chat_service_picks_admin_door_access_over_it_system_permission_when_query_matches_admin(
    monkeypatch,
) -> None:
    admin_item = _seed_by_id("admin-faq-003")
    it_item = _seed_by_id("it-faq-012")

    fake_lexical = _FakeLexicalRetriever(
        [_build_fixture_lexical_hit(admin_item, score=2.3)]
    )
    fake_hybrid = _FakeHybridRetriever(
        [
            _build_fixture_hybrid_hit(
                it_item,
                score=0.033,
                lexical_rank=1,
                vector_rank=1,
                rrf_rank=1,
                bm25_score=2.5,
                vector_score=0.87,
            ),
            _build_fixture_hybrid_hit(
                admin_item,
                score=0.031,
                lexical_rank=2,
                vector_rank=2,
                rrf_rank=2,
                bm25_score=2.4,
                vector_score=0.85,
            ),
        ]
    )
    fake_planner = _FakePlanner(
        PlannerOutput(
            normalized_query="门禁权限怎么申请？",
            domain_hint=None,
            lexical_terms=["门禁", "权限", "申请"],
            planner_confidence=0.85,
        )
    )

    _install_fakes(
        monkeypatch, lexical=fake_lexical, hybrid=fake_hybrid, planner=fake_planner
    )

    service = ChatService()
    response = service.ask(
        ChatAskRequest(raw_query="门禁权限怎么申请？", debug=True),
        trace_id="trace-phase2-cross-domain-admin-door",
        debug_enabled=True,
    )

    assert response.response_status == "ok"
    assert len(response.citations) == 1
    assert response.citations[0].citation_id == "admin-faq-003"
    assert response.citations[0].source_locator == admin_item["source_locator"]
    assert response.debug_info is not None
    assert response.debug_info.rerank_accept is True
    assert response.debug_info.retrieved_chunks == ["admin-faq-003"]
    assert "it-faq-012" not in [c.citation_id for c in response.citations]


def test_chat_service_picks_it_system_permission_over_admin_door_access_when_query_matches_it(
    monkeypatch,
) -> None:
    admin_item = _seed_by_id("admin-faq-003")
    it_item = _seed_by_id("it-faq-012")

    fake_lexical = _FakeLexicalRetriever(
        [_build_fixture_lexical_hit(it_item, score=2.3)]
    )
    fake_hybrid = _FakeHybridRetriever(
        [
            _build_fixture_hybrid_hit(
                admin_item,
                score=0.033,
                lexical_rank=1,
                vector_rank=1,
                rrf_rank=1,
                bm25_score=2.5,
                vector_score=0.87,
            ),
            _build_fixture_hybrid_hit(
                it_item,
                score=0.031,
                lexical_rank=2,
                vector_rank=2,
                rrf_rank=2,
                bm25_score=2.4,
                vector_score=0.85,
            ),
        ]
    )
    fake_planner = _FakePlanner(
        PlannerOutput(
            normalized_query="如何申请系统权限开通？",
            domain_hint=None,
            lexical_terms=["系统", "权限", "开通", "申请"],
            planner_confidence=0.85,
        )
    )

    _install_fakes(
        monkeypatch, lexical=fake_lexical, hybrid=fake_hybrid, planner=fake_planner
    )

    service = ChatService()
    response = service.ask(
        ChatAskRequest(raw_query="如何申请系统权限开通？", debug=True),
        trace_id="trace-phase2-cross-domain-it-system-permission",
        debug_enabled=True,
    )

    assert response.response_status == "ok"
    assert len(response.citations) == 1
    assert response.citations[0].citation_id == "it-faq-012"
    assert response.citations[0].source_locator == it_item["source_locator"]
    assert response.debug_info is not None
    assert response.debug_info.rerank_accept is True
    assert response.debug_info.retrieved_chunks == ["it-faq-012"]
    assert "admin-faq-003" not in [c.citation_id for c in response.citations]


# ---------------------------------------------------------------------------
# Finance × Ops 申请审批 symmetric contamination pair
#
#   finance-faq-005 "借款申请怎么走？"
#   ops-faq-003     "生产变更需要怎么申请？"
#
# Both answer "按流程提交/发起申请...并提交审批". This is the last
# cross-domain pair in §9.4's named list that has enough structural
# parallelism in the current fixture set to support a load-bearing
# symmetric test. After this pair lands, §9.4 is considered saturated
# at the existing fixture data; remaining directions (HR × IT, Admin ×
# 其他) are fixture data-gaps — not test gaps — and need seed additions
# before more tests can be added.
# ---------------------------------------------------------------------------


def test_chat_service_picks_finance_loan_application_over_ops_production_change_when_query_matches_finance(
    monkeypatch,
) -> None:
    finance_item = _seed_by_id("finance-faq-005")
    ops_item = _seed_by_id("ops-faq-003")

    fake_lexical = _FakeLexicalRetriever(
        [_build_fixture_lexical_hit(finance_item, score=2.3)]
    )
    fake_hybrid = _FakeHybridRetriever(
        [
            _build_fixture_hybrid_hit(
                ops_item,
                score=0.033,
                lexical_rank=1,
                vector_rank=1,
                rrf_rank=1,
                bm25_score=2.5,
                vector_score=0.87,
            ),
            _build_fixture_hybrid_hit(
                finance_item,
                score=0.031,
                lexical_rank=2,
                vector_rank=2,
                rrf_rank=2,
                bm25_score=2.4,
                vector_score=0.85,
            ),
        ]
    )
    fake_planner = _FakePlanner(
        PlannerOutput(
            normalized_query="借款申请怎么走？",
            domain_hint=None,
            lexical_terms=["借款", "申请", "流程"],
            planner_confidence=0.85,
        )
    )

    _install_fakes(
        monkeypatch, lexical=fake_lexical, hybrid=fake_hybrid, planner=fake_planner
    )

    service = ChatService()
    response = service.ask(
        ChatAskRequest(raw_query="借款申请怎么走？", debug=True),
        trace_id="trace-phase2-cross-domain-finance-loan",
        debug_enabled=True,
    )

    assert response.response_status == "ok"
    assert len(response.citations) == 1
    assert response.citations[0].citation_id == "finance-faq-005"
    assert response.citations[0].source_locator == finance_item["source_locator"]
    assert response.debug_info is not None
    assert response.debug_info.rerank_accept is True
    assert response.debug_info.retrieved_chunks == ["finance-faq-005"]
    assert "ops-faq-003" not in [c.citation_id for c in response.citations]


def test_chat_service_picks_ops_production_change_over_finance_loan_application_when_query_matches_ops(
    monkeypatch,
) -> None:
    finance_item = _seed_by_id("finance-faq-005")
    ops_item = _seed_by_id("ops-faq-003")

    fake_lexical = _FakeLexicalRetriever(
        [_build_fixture_lexical_hit(ops_item, score=2.3)]
    )
    fake_hybrid = _FakeHybridRetriever(
        [
            _build_fixture_hybrid_hit(
                finance_item,
                score=0.033,
                lexical_rank=1,
                vector_rank=1,
                rrf_rank=1,
                bm25_score=2.5,
                vector_score=0.87,
            ),
            _build_fixture_hybrid_hit(
                ops_item,
                score=0.031,
                lexical_rank=2,
                vector_rank=2,
                rrf_rank=2,
                bm25_score=2.4,
                vector_score=0.85,
            ),
        ]
    )
    fake_planner = _FakePlanner(
        PlannerOutput(
            normalized_query="生产变更需要怎么申请？",
            domain_hint=None,
            lexical_terms=["生产变更", "申请", "审批"],
            planner_confidence=0.85,
        )
    )

    _install_fakes(
        monkeypatch, lexical=fake_lexical, hybrid=fake_hybrid, planner=fake_planner
    )

    service = ChatService()
    response = service.ask(
        ChatAskRequest(raw_query="生产变更需要怎么申请？", debug=True),
        trace_id="trace-phase2-cross-domain-ops-production-change",
        debug_enabled=True,
    )

    assert response.response_status == "ok"
    assert len(response.citations) == 1
    assert response.citations[0].citation_id == "ops-faq-003"
    assert response.citations[0].source_locator == ops_item["source_locator"]
    assert response.debug_info is not None
    assert response.debug_info.rerank_accept is True
    assert response.debug_info.retrieved_chunks == ["ops-faq-003"]
    assert "finance-faq-005" not in [c.citation_id for c in response.citations]


# ---------------------------------------------------------------------------
# HR × IT 登录 symmetric contamination pair
#
#   hr-faq-013 "HR 系统登录不上怎么办？"         (added this round)
#   it-faq-001 "忘记登录密码怎么办？"
#
# HR fixtures previously had no login/account management FAQ structurally
# parallel to the IT side, which forced the HR × IT direction of §9.4 to
# be marked as a fixture data-gap. This round adds hr-faq-013 so the pair
# is now testable against real seed data.
#
# Both answers follow the same template: "如 X 可先 Y ... 若仍 Z，请通过
# ... 入口提交申请，由管理员按流程协助处理". A user query like
# "登录不上怎么办" is genuinely ambiguous between the HR self-service
# system and general IT/company-account login — both directions must
# resolve to their own domain answer.
# ---------------------------------------------------------------------------


def test_chat_service_picks_hr_self_service_login_over_it_password_reset_when_query_matches_hr(
    monkeypatch,
) -> None:
    hr_item = _seed_by_id("hr-faq-013")
    it_item = _seed_by_id("it-faq-001")

    fake_lexical = _FakeLexicalRetriever(
        [_build_fixture_lexical_hit(hr_item, score=2.3)]
    )
    fake_hybrid = _FakeHybridRetriever(
        [
            _build_fixture_hybrid_hit(
                it_item,
                score=0.033,
                lexical_rank=1,
                vector_rank=1,
                rrf_rank=1,
                bm25_score=2.5,
                vector_score=0.87,
            ),
            _build_fixture_hybrid_hit(
                hr_item,
                score=0.031,
                lexical_rank=2,
                vector_rank=2,
                rrf_rank=2,
                bm25_score=2.4,
                vector_score=0.85,
            ),
        ]
    )
    fake_planner = _FakePlanner(
        PlannerOutput(
            normalized_query="HR 系统登录不上怎么办？",
            domain_hint=None,
            lexical_terms=["HR 系统", "登录", "账号"],
            planner_confidence=0.85,
        )
    )

    _install_fakes(
        monkeypatch, lexical=fake_lexical, hybrid=fake_hybrid, planner=fake_planner
    )

    service = ChatService()
    response = service.ask(
        ChatAskRequest(raw_query="HR 系统登录不上怎么办？", debug=True),
        trace_id="trace-phase2-cross-domain-hr-login",
        debug_enabled=True,
    )

    assert response.response_status == "ok"
    assert len(response.citations) == 1
    assert response.citations[0].citation_id == "hr-faq-013"
    assert response.citations[0].source_locator == hr_item["source_locator"]
    assert response.debug_info is not None
    assert response.debug_info.rerank_accept is True
    assert response.debug_info.retrieved_chunks == ["hr-faq-013"]
    assert "it-faq-001" not in [c.citation_id for c in response.citations]


def test_chat_service_picks_it_password_reset_over_hr_self_service_login_when_query_matches_it(
    monkeypatch,
) -> None:
    hr_item = _seed_by_id("hr-faq-013")
    it_item = _seed_by_id("it-faq-001")

    fake_lexical = _FakeLexicalRetriever(
        [_build_fixture_lexical_hit(it_item, score=2.3)]
    )
    fake_hybrid = _FakeHybridRetriever(
        [
            _build_fixture_hybrid_hit(
                hr_item,
                score=0.033,
                lexical_rank=1,
                vector_rank=1,
                rrf_rank=1,
                bm25_score=2.5,
                vector_score=0.87,
            ),
            _build_fixture_hybrid_hit(
                it_item,
                score=0.031,
                lexical_rank=2,
                vector_rank=2,
                rrf_rank=2,
                bm25_score=2.4,
                vector_score=0.85,
            ),
        ]
    )
    fake_planner = _FakePlanner(
        PlannerOutput(
            normalized_query="忘记登录密码怎么办？",
            domain_hint=None,
            lexical_terms=["忘记", "登录", "密码"],
            planner_confidence=0.85,
        )
    )

    _install_fakes(
        monkeypatch, lexical=fake_lexical, hybrid=fake_hybrid, planner=fake_planner
    )

    service = ChatService()
    response = service.ask(
        ChatAskRequest(raw_query="忘记登录密码怎么办？", debug=True),
        trace_id="trace-phase2-cross-domain-it-password",
        debug_enabled=True,
    )

    assert response.response_status == "ok"
    assert len(response.citations) == 1
    assert response.citations[0].citation_id == "it-faq-001"
    assert response.citations[0].source_locator == it_item["source_locator"]
    assert response.debug_info is not None
    assert response.debug_info.rerank_accept is True
    assert response.debug_info.retrieved_chunks == ["it-faq-001"]
    assert "hr-faq-013" not in [c.citation_id for c in response.citations]
