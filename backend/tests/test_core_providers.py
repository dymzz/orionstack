import json

import httpx
import pytest
from pydantic import ValidationError

from app.config.core_settings import CoreConfigurationError, CoreSettings
from app.decision.deepseek import DeepSeekClient
from app.decision.jev import JevClient, ScoreQuestion
from app.decision.providers import ProviderError
from app.integration.contracts import ActionRequest, EventRequest
from app.knowledge.contracts import AccessContext, EvidenceCandidate, QueryContext, SourceRef, content_hash


def config():
    return CoreSettings(typesafe_api_key="fake-jev-secret", deepseek_api_key="fake-deepseek-secret")


def candidate(evidence_id="e-1", *, tenant="t1", scope="internal"):
    return EvidenceCandidate(
        evidence_id=evidence_id, evidence_kind="document_chunk", tenant_id=tenant, access_scope=scope,
        source=SourceRef(source_id="s-1", source_version="v1", source_locator="uploads/policy.md#1",
                         document_id="doc-1", document_version="v1", chunk_id="chunk-1"),
        text="年假需要主管批准。", retrieval_method="vector", typed_values={"days": 5},
    )


ACCESS = AccessContext(tenant_id="t1", user_id="u-1")
QUERY = QueryContext(query="如何申请年假？")


def transport(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def route_response(**overrides):
    answer = {"type": "choice", "choice": "both",
              "probabilities": {"structured": 0.1, "vector": 0.2, "both": 0.7}, "confidence": 0.5}
    answer.update(overrides)
    return {"model": "jev-1.13.0", "usage": {"input_tokens": 10, "output_tokens": 4},
            "answers": {"strategy": answer}}


def deepseek_response(draft=None, **choice_overrides):
    if draft is None:
        draft = {"status": "answered", "answer": "提交申请，等待主管批准。", "citations": ["e-1"]}
    choice = {"finish_reason": "stop", "message": {"role": "assistant", "content": json.dumps(draft)}}
    choice.update(choice_overrides)
    return {"model": "deepseek-flash", "usage": {"prompt_tokens": 50, "completion_tokens": 20},
            "choices": [choice]}


def test_env_config_reads_native_keys_and_redacts_repr(monkeypatch):
    monkeypatch.setenv("ORIONSTACK_DATABASE_URL", "postgresql://person:private@localhost/core")
    monkeypatch.setenv("TYPESAFE_API_KEY", "native-jev-key")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "native-deepseek-key")
    settings = CoreSettings()
    assert settings.require_database_url().endswith("/core")
    assert settings.require_typesafe_key() == "native-jev-key"
    assert settings.require_deepseek_key() == "native-deepseek-key"
    assert all(settings.configuration_status()[name] for name in
               ("database_configured", "typesafe_configured", "deepseek_configured"))
    assert not any(secret in repr(settings) for secret in ("private", "native-jev-key", "native-deepseek-key"))


@pytest.mark.parametrize("method,name", [
    ("require_database_url", "ORIONSTACK_DATABASE_URL"),
    ("require_typesafe_key", "TYPESAFE_API_KEY"), ("require_deepseek_key", "DEEPSEEK_API_KEY"),
])
def test_missing_configuration_fails_with_variable_name(method, name):
    settings = CoreSettings(database_url="", typesafe_api_key="", deepseek_api_key="")
    with pytest.raises(CoreConfigurationError, match=name):
        getattr(settings, method)()


@pytest.mark.parametrize("timeout", [0, -1, float("nan"), float("inf")])
def test_invalid_timeout_is_rejected(timeout):
    with pytest.raises(CoreConfigurationError):
        CoreSettings(provider_timeout_seconds=timeout)


def test_jev_routing_uses_native_api_contract():
    def handler(request):
        assert str(request.url) == "https://api.typesafe.ai/v1/systemone"
        assert request.headers["authorization"] == "Bearer fake-jev-secret"
        body = json.loads(request.content)
        assert body["model"] == "jev-1.13.0"
        assert body["state"]["query"] == QUERY.query
        assert set(body["questions"]["strategy"]["criteria"]) == {"structured", "vector", "both"}
        return httpx.Response(200, json=route_response())
    with transport(handler) as client:
        decision = JevClient(config(), client).decide(QUERY)
    assert decision.strategy == "both"
    assert decision.usage.input_tokens == 10


@pytest.mark.parametrize("overrides", [
    {"choice": "workflow"}, {"choice": "vector"}, {"type": "noul", "noul": 0.5},
    {"probabilities": {"structured": 0.1, "vector": 0.1, "both": 0.1}},
    {"probabilities": {"structured": 0, "vector": 0, "unknown": 1}},
    {"confidence": float("nan")}, {"confidence": True},
])
def test_invalid_jev_decision_is_rejected(overrides):
    with transport(lambda _: httpx.Response(200, content=json.dumps(route_response(**overrides)))) as client:
        with pytest.raises(ProviderError):
            JevClient(config(), client).decide(QUERY)


def test_jev_requires_exact_question_ids():
    response = route_response()
    response["answers"]["invented"] = {"type": "noul", "noul": 1}
    with transport(lambda _: httpx.Response(200, json=response)) as client:
        with pytest.raises(ProviderError, match="invalid_response"):
            JevClient(config(), client).decide(QUERY)


def test_evidence_rubric_references_each_state_index_and_score_is_not_probability():
    def handler(request):
        body = json.loads(request.content)
        answers = {}
        for index in range(2):
            question = body["questions"][f"relevance_{index}"]
            assert f"state.evidence[{index}]" in question["instructions"]
            answers[f"relevance_{index}"] = {
                "type": "score", "score": 2.8, "confidence": 0.8,
                "legend": {str(i): level for i, level in enumerate(question["criteria"])},
                "probabilities": {"0": 0, "1": 0, "2": 0.2, "3": 0.8},
            }
            answers[f"support_{index}"] = {"type": "noul", "noul": 0.9}
        return httpx.Response(200, json={"model": "jev-1.13.0", "answers": answers,
                                        "usage": {"input_tokens": 80, "output_tokens": 15}})
    with transport(handler) as client:
        judgments, result = JevClient(config(), client).judge_evidence(QUERY, (candidate(), candidate("e-2")), ACCESS)
    assert [judgment.evidence_id for judgment in judgments] == ["e-1", "e-2"]
    assert judgments[0].relevance.score == 2.8
    assert result.usage.output_tokens == 15


def test_score_distribution_must_match_weighted_value():
    response = {"model": "jev-1.13.0", "usage": {"input_tokens": 2, "output_tokens": 3},
                "answers": {"rating": {"type": "score", "score": 1.0, "confidence": 1,
                                       "legend": {"0": "no", "1": "yes"},
                                       "probabilities": {"0": 1, "1": 0}}}}
    with transport(lambda _: httpx.Response(200, json=response)) as client:
        with pytest.raises(ProviderError):
            JevClient(config(), client).evaluate("data", {"rating": ScoreQuestion(instructions="Rate", criteria=("no", "yes"))})


def test_sufficiency_is_judged_on_selected_set():
    def handler(request):
        body = json.loads(request.content)
        assert set(body["questions"]) == {"sufficient"}
        assert len(body["state"]["evidence"]) == 2
        return httpx.Response(200, json={"model": "jev-1.13.0", "usage": {"input_tokens": 4, "output_tokens": 2},
                                        "answers": {"sufficient": {"type": "noul", "noul": 0.95}}})
    with transport(handler) as client:
        result = JevClient(config(), client).sufficiency(QUERY, (candidate(), candidate("e-2")), ACCESS)
    assert result.answers["sufficient"].noul == 0.95


@pytest.mark.parametrize("provider", ["jev", "deepseek"])
@pytest.mark.parametrize("status", [401, 422, 429, 529, 302])
def test_http_failure_redacts_bodies_and_does_not_follow_redirect(provider, status):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(status, text="fake-jev-secret fake-deepseek-secret private-response", headers={"location": "https://example.com"})
    with transport(handler) as client:
        with pytest.raises(ProviderError) as error:
            if provider == "jev":
                JevClient(config(), client).decide(QUERY)
            else:
                DeepSeekClient(config(), client).generate(QUERY, (candidate(),), ACCESS)
    assert error.value.status_code == status
    assert "secret" not in str(error.value)
    assert "private-response" not in str(error.value)
    assert len(calls) == 1


def test_timeout_error_does_not_leak_driver_message():
    def handler(request):
        raise httpx.ReadTimeout("fake-jev-secret", request=request)
    with transport(handler) as client:
        with pytest.raises(ProviderError, match="jev: timeout") as error:
            JevClient(config(), client).decide(QUERY)
    assert "fake-jev-secret" not in str(error.value)


def test_deepseek_answer_has_backend_citation_metadata():
    def handler(request):
        assert str(request.url) == "https://api.deepseek.com/chat/completions"
        assert request.headers["authorization"] == "Bearer fake-deepseek-secret"
        body = json.loads(request.content)
        assert body["response_format"] == {"type": "json_object"}
        assert body["thinking"] == {"type": "disabled"}
        assert "source_locator" not in body["messages"][1]["content"]
        return httpx.Response(200, json=deepseek_response())
    with transport(handler) as client:
        answer = DeepSeekClient(config(), client).generate(QUERY, (candidate(),), ACCESS)
    assert answer.status == "answered"
    assert answer.citations[0].source == candidate().source
    assert answer.usage.output_tokens == 20


@pytest.mark.parametrize("draft", [
    {"status": "answered", "answer": "ok", "citations": ["invented"]},
    {"status": "answered", "answer": "ok", "citations": []},
    {"status": "answered", "answer": "ok", "citations": ["e-1", "e-1"]},
    {"status": "answered", "answer": " ", "citations": ["e-1"]},
    {"status": "answered", "answer": "ok", "citations": ["e-1"], "source_locator": "fake"},
    {"status": "insufficient_evidence", "answer": "uncertain", "citations": ["e-1"]},
])
def test_hallucinated_or_empty_citations_and_metadata_are_rejected(draft):
    with transport(lambda _: httpx.Response(200, json=deepseek_response(draft))) as client:
        with pytest.raises(ProviderError, match="invalid_response"):
            DeepSeekClient(config(), client).generate(QUERY, (candidate(),), ACCESS)


@pytest.mark.parametrize("reason", ["length", "content_filter", "tool_calls"])
def test_incomplete_generation_is_rejected(reason):
    with transport(lambda _: httpx.Response(200, json=deepseek_response(finish_reason=reason))) as client:
        with pytest.raises(ProviderError):
            DeepSeekClient(config(), client).generate(QUERY, (candidate(),), ACCESS)


@pytest.mark.parametrize("bad_content", ["", "not json", '{"answer":"a","answer":"b"}', '{"answer":NaN}'])
def test_invalid_json_generation_is_rejected(bad_content):
    response = deepseek_response(message={"role": "assistant", "content": bad_content})
    with transport(lambda _: httpx.Response(200, json=response)) as client:
        with pytest.raises(ProviderError):
            DeepSeekClient(config(), client).generate(QUERY, (candidate(),), ACCESS)


def test_no_evidence_short_circuits_without_keys_or_network():
    def handler(_):
        pytest.fail("Empty evidence must not call a provider")
    with transport(handler) as client:
        settings = CoreSettings(typesafe_api_key="", deepseek_api_key="")
        assert JevClient(settings, client).judge_evidence(QUERY, (), ACCESS) == ((), None)
        assert JevClient(settings, client).sufficiency(QUERY, (), ACCESS) is None
        assert DeepSeekClient(settings, client).generate(QUERY, (), ACCESS).status == "insufficient_evidence"


@pytest.mark.parametrize("evidence", [candidate(tenant="other"), candidate(scope="restricted")])
def test_authorization_blocks_evidence_before_provider_call(evidence):
    def handler(_):
        pytest.fail("Unauthorized evidence must not be sent to providers")
    with transport(handler) as client:
        with pytest.raises(PermissionError):
            JevClient(config(), client).judge_evidence(QUERY, (evidence,), ACCESS)
        with pytest.raises(PermissionError):
            DeepSeekClient(config(), client).generate(QUERY, (evidence,), ACCESS)


def test_duplicate_evidence_ids_are_rejected():
    with pytest.raises(ValueError, match="Duplicate evidence"):
        DeepSeekClient(config()).generate(QUERY, (candidate(), candidate()), ACCESS)


def test_workflow_action_schema_has_canonical_fingerprint_and_no_auth_override():
    raw = {"action": "create_ticket", "entity": {"type": "employee", "id": "EMP-00128"},
           "parameters": {"category": "account_access", "priority": "normal"}, "context": {"request_id": "req-1"}}
    request = ActionRequest.model_validate(raw)
    reordered = dict(raw, parameters={"priority": "normal", "category": "account_access"})
    assert request.payload_fingerprint() == ActionRequest.model_validate(reordered).payload_fingerprint()
    assert request.payload_fingerprint() != request.model_copy(update={"parameters": {"priority": "high"}}).payload_fingerprint()
    with pytest.raises(ValidationError):
        ActionRequest.model_validate(dict(raw, context={"request_id": "req-1", "tenant_id": "other"}))


def test_event_requires_explicit_timezone_and_source_version():
    raw = {"event_id": "evt-1", "event_type": "entity.updated", "occurred_at": "2026-10-02T10:00:00+08:00",
           "source": {"namespace": "crm", "record_id": "EMP-1", "version": "2"}, "payload": {}}
    assert EventRequest.model_validate(raw).source.version == "2"
    with pytest.raises(ValidationError):
        EventRequest.model_validate(dict(raw, occurred_at="2026-10-02T10:00:00"))
    with pytest.raises(ValidationError):
        EventRequest.model_validate(dict(raw, schema_version="2"))


def test_full_hash_tracks_exact_content_without_merging_source_identity():
    assert len(content_hash("同一内容")) == 64
    assert content_hash("line\n") != content_hash("line\r\n")
    assert candidate().model_copy(update={"source": SourceRef(source_id="different", source_version="v1", source_locator="other")}).source.source_id != candidate().source.source_id


@pytest.mark.parametrize('provider,body,code', [
    ('workers_ai', {'errors':[{'code':4006,'message':'fake-secret daily quota'}]}, 'daily_allocation_exhausted'),
    ('workers_ai', {'errors':[{'code':4000,'message':'fake-secret rate limit'}]}, 'rate_limited'),
    ('workers_ai', None, 'rate_limited'),
    ('jev', {'errors':[{'code':4006,'message':'fake-secret'}]}, 'http_error'),
])
def test_provider_quota_is_distinguished_from_transient_limits_without_error_body_leaks(provider,body,code):
    from app.providers.http import post_json
    response=httpx.Response(429,json=body) if body is not None else httpx.Response(429,content=b'fake-secret malformed response')
    with transport(lambda _:response) as client:
        with pytest.raises(ProviderError) as failure:
            post_json(provider,'https://example.invalid/ai','fake-secret',{'text':['synthetic']},30,client)
    assert failure.value.code==code and failure.value.status_code==429
    assert 'fake-secret' not in str(failure.value)
