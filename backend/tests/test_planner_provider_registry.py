from __future__ import annotations

from app.query.query_planner import PlannerOutput, QueryPlanner


class _StubProvider:
    def __init__(self, name: str) -> None:
        self.name = name

    def plan(self, normalized_query: str) -> PlannerOutput:
        return PlannerOutput(
            normalized_query=normalized_query,
            domain_hint=None,
            lexical_terms=[normalized_query] if normalized_query else [],
            planner_confidence=0.9,
        )


def test_query_planner_accepts_openai_compatible_provider(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.query.providers.build_planner_provider",
        lambda name, settings: _StubProvider(name),
    )
    planner = QueryPlanner(provider="openai_compatible")
    output = planner.plan("请假流程")
    assert planner.router_name == "query_planner_openai_compatible"
    assert output.lexical_terms == ["请假流程"]


def test_query_planner_accepts_llama_cpp_provider(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.query.providers.build_planner_provider",
        lambda name, settings: _StubProvider(name),
    )
    planner = QueryPlanner(provider="llama_cpp")
    output = planner.plan("VPN无法连接")
    assert planner.router_name == "query_planner_llama_cpp"
    assert output.lexical_terms == ["VPN无法连接"]
