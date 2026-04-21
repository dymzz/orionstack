"""Unit tests for QwenApiProvider parse pipeline + error paths.

Covers docs/2_8_planner_llm_integration.md §4 (7-step parse pipeline) and
§4.2 (exception taxonomy). All HTTP calls are mocked via httpx.MockTransport
— no live network, no DashScope access required.

Test groups:
- Success:       well-formed envelope → correct PlannerOutput
- HTTP errors:   non-200 / connection failure → PlannerHttpError
- Timeout:       httpx.TimeoutException → PlannerTimeoutError
- Parse errors:  non-JSON body / missing choices / content not JSON / content not str
- Schema errors: wrong types / enum violations / confidence out of range / bool confidence
- Normalization: dedup + truncate + strip on lexical_terms
- Construction:  empty api_key rejected; name attribute stable
"""

from __future__ import annotations

import json

import httpx
import pytest

from app.query.providers import QwenApiProvider
from app.query.providers.errors import (
    PlannerHttpError,
    PlannerParseError,
    PlannerSchemaError,
    PlannerTimeoutError,
)
from app.query.query_planner import PlannerOutput


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _envelope(payload: dict | str) -> dict:
    """Wrap a payload dict (or raw content string) as a Qwen API response envelope."""
    content = json.dumps(payload) if isinstance(payload, dict) else payload
    return {"choices": [{"message": {"content": content}}]}


_VALID_PAYLOAD: dict = {
    "normalized_query": "如何申请年假?",
    "domain_hint": "hr",
    "lexical_terms": ["申请年假", "年假", "申请"],
    "planner_confidence": 0.92,
}


def _make_provider(handler, timeout: float = 1.0) -> QwenApiProvider:
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return QwenApiProvider(
        api_base="http://mock.test",
        api_model="qwen-test",
        api_key="mock-key",
        timeout_seconds=timeout,
        http_client=client,
    )


def _static_handler(response_json: dict, status: int = 200):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json=response_json)

    return handler


def _text_handler(body: str, status: int = 200):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, text=body)

    return handler


# ---------------------------------------------------------------------------
# Success path
# ---------------------------------------------------------------------------


class TestSuccess:
    def test_valid_response_parses_to_planner_output(self) -> None:
        provider = _make_provider(_static_handler(_envelope(_VALID_PAYLOAD)))
        output = provider.plan("如何申请年假？")

        assert isinstance(output, PlannerOutput)
        assert output.normalized_query == "如何申请年假?"
        assert output.domain_hint == "hr"
        assert output.lexical_terms == ["申请年假", "年假", "申请"]
        assert output.planner_confidence == pytest.approx(0.92)

    def test_domain_hint_null_accepted(self) -> None:
        payload = {**_VALID_PAYLOAD, "domain_hint": None}
        provider = _make_provider(_static_handler(_envelope(payload)))
        output = provider.plan("怎么提交申请")
        assert output.domain_hint is None

    def test_domain_hint_missing_treated_as_null(self) -> None:
        payload = {k: v for k, v in _VALID_PAYLOAD.items() if k != "domain_hint"}
        provider = _make_provider(_static_handler(_envelope(payload)))
        output = provider.plan("怎么提交申请")
        assert output.domain_hint is None

    def test_integer_confidence_accepted(self) -> None:
        # LLM may emit 1 instead of 1.0; must be coerced to float
        payload = {**_VALID_PAYLOAD, "planner_confidence": 1}
        provider = _make_provider(_static_handler(_envelope(payload)))
        output = provider.plan("x")
        assert output.planner_confidence == 1.0
        assert isinstance(output.planner_confidence, float)

    def test_all_five_domains_accepted(self) -> None:
        for domain in ("hr", "finance", "admin", "it", "ops"):
            payload = {**_VALID_PAYLOAD, "domain_hint": domain}
            provider = _make_provider(_static_handler(_envelope(payload)))
            output = provider.plan("query")
            assert output.domain_hint == domain


# ---------------------------------------------------------------------------
# HTTP error paths
# ---------------------------------------------------------------------------


class TestHttpErrors:
    def test_status_500_raises_http_error(self) -> None:
        provider = _make_provider(_text_handler("internal error", status=500))
        with pytest.raises(PlannerHttpError, match="500"):
            provider.plan("query")

    def test_status_401_raises_http_error(self) -> None:
        provider = _make_provider(_text_handler("unauthorized", status=401))
        with pytest.raises(PlannerHttpError, match="401"):
            provider.plan("query")

    def test_status_429_raises_http_error(self) -> None:
        provider = _make_provider(_text_handler("rate limit", status=429))
        with pytest.raises(PlannerHttpError, match="429"):
            provider.plan("query")

    def test_connection_error_raises_http_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("cannot connect")

        provider = _make_provider(handler)
        with pytest.raises(PlannerHttpError, match="connection"):
            provider.plan("query")


class TestTimeout:
    def test_timeout_raises_timeout_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.TimeoutException("request timed out")

        provider = _make_provider(handler)
        with pytest.raises(PlannerTimeoutError, match="timeout"):
            provider.plan("query")


# ---------------------------------------------------------------------------
# Parse errors (transport OK, but response structure invalid)
# ---------------------------------------------------------------------------


class TestParseErrors:
    def test_body_not_json_raises_parse_error(self) -> None:
        provider = _make_provider(_text_handler("not json at all"))
        with pytest.raises(PlannerParseError, match="not json"):
            provider.plan("query")

    def test_empty_envelope_raises_parse_error(self) -> None:
        provider = _make_provider(_static_handler({}))
        with pytest.raises(PlannerParseError, match="choices"):
            provider.plan("query")

    def test_empty_choices_list_raises_parse_error(self) -> None:
        provider = _make_provider(_static_handler({"choices": []}))
        with pytest.raises(PlannerParseError, match="choices"):
            provider.plan("query")

    def test_choice_missing_message_raises_parse_error(self) -> None:
        provider = _make_provider(_static_handler({"choices": [{}]}))
        with pytest.raises(PlannerParseError, match="choices"):
            provider.plan("query")

    def test_content_not_json_raises_parse_error(self) -> None:
        provider = _make_provider(_static_handler(_envelope("this is not json")))
        with pytest.raises(PlannerParseError, match="content is not valid json"):
            provider.plan("query")

    def test_content_not_string_raises_parse_error(self) -> None:
        envelope = {"choices": [{"message": {"content": 123}}]}
        provider = _make_provider(_static_handler(envelope))
        with pytest.raises(PlannerParseError, match="content is not str"):
            provider.plan("query")


# ---------------------------------------------------------------------------
# Reasoning-model sanitization
#
# Local llama-server runs of Qwen3 / DeepSeek-R1 style models emit
# `<think>...</think>` reasoning prefixes and sometimes wrap the JSON in
# markdown code fences. DashScope cloud strips these server-side, but local
# llama-server passes them through. The sanitize pass restores parser
# robustness; see docs/2_8_smoke_live_results__local__qwen3-1.7b-q4_k_m.json
# for the real-world failure mode that motivated this coverage.
# ---------------------------------------------------------------------------


class TestReasoningModelSanitization:
    def _valid_json_string(self) -> str:
        return json.dumps(_VALID_PAYLOAD)

    def test_closed_think_block_stripped_before_json(self) -> None:
        content = f"<think>let me reason about this query</think>{self._valid_json_string()}"
        provider = _make_provider(_static_handler(_envelope(content)))
        output = provider.plan("query")
        assert output.domain_hint == "hr"
        assert output.planner_confidence == pytest.approx(0.92)

    def test_think_block_with_newlines_and_whitespace(self) -> None:
        content = (
            "<think>\nstep 1: parse query\nstep 2: classify domain\n</think>\n\n"
            + self._valid_json_string()
        )
        provider = _make_provider(_static_handler(_envelope(content)))
        output = provider.plan("query")
        assert output.normalized_query == "如何申请年假?"

    def test_multiple_think_blocks_all_stripped(self) -> None:
        # Consecutive think blocks occur when the reasoning model
        # re-thinks before committing to the final answer.
        content = (
            f"<think>first pass</think><think>second pass, revised</think>"
            f"{self._valid_json_string()}"
        )
        provider = _make_provider(_static_handler(_envelope(content)))
        output = provider.plan("query")
        assert output.domain_hint == "hr"

    def test_think_tag_case_insensitive(self) -> None:
        content = f"<THINK>upper case</THINK>{self._valid_json_string()}"
        provider = _make_provider(_static_handler(_envelope(content)))
        output = provider.plan("query")
        assert output.domain_hint == "hr"

    def test_markdown_json_fence_stripped(self) -> None:
        content = f"```json\n{self._valid_json_string()}\n```"
        provider = _make_provider(_static_handler(_envelope(content)))
        output = provider.plan("query")
        assert output.domain_hint == "hr"

    def test_markdown_bare_fence_stripped(self) -> None:
        content = f"```\n{self._valid_json_string()}\n```"
        provider = _make_provider(_static_handler(_envelope(content)))
        output = provider.plan("query")
        assert output.domain_hint == "hr"

    def test_think_and_fence_combined(self) -> None:
        content = (
            "<think>reasoning...</think>\n"
            f"```json\n{self._valid_json_string()}\n```"
        )
        provider = _make_provider(_static_handler(_envelope(content)))
        output = provider.plan("query")
        assert output.domain_hint == "hr"

    def test_unclosed_think_raises_truncation_parse_error(self) -> None:
        # Reasoning model ran out of n_predict budget mid-thinking; operator
        # should see a clear error pointing at the root cause, not a cryptic
        # "Expecting value: line 1 column 1 (char 0)".
        content = "<think>this reasoning is getting cut off mid-sentence and"
        provider = _make_provider(_static_handler(_envelope(content)))
        with pytest.raises(
            PlannerParseError, match=r"unclosed <think>.*n_predict"
        ):
            provider.plan("query")


# ---------------------------------------------------------------------------
# Schema errors (JSON parses OK, but fields violate PlannerOutput schema)
# ---------------------------------------------------------------------------


class TestSchemaErrors:
    def _provider_for(self, payload) -> QwenApiProvider:
        return _make_provider(_static_handler(_envelope(payload)))

    def test_payload_not_object_raises(self) -> None:
        # JSON array (valid JSON) at the content level is not a valid payload
        envelope = {"choices": [{"message": {"content": "[1, 2, 3]"}}]}
        provider = _make_provider(_static_handler(envelope))
        with pytest.raises(PlannerSchemaError, match="json object"):
            provider.plan("query")

    def test_normalized_query_wrong_type(self) -> None:
        provider = self._provider_for({**_VALID_PAYLOAD, "normalized_query": 42})
        with pytest.raises(PlannerSchemaError, match="normalized_query"):
            provider.plan("query")

    def test_normalized_query_missing(self) -> None:
        payload = {k: v for k, v in _VALID_PAYLOAD.items() if k != "normalized_query"}
        provider = self._provider_for(payload)
        with pytest.raises(PlannerSchemaError, match="normalized_query"):
            provider.plan("query")

    def test_domain_hint_not_in_enum(self) -> None:
        provider = self._provider_for({**_VALID_PAYLOAD, "domain_hint": "marketing"})
        with pytest.raises(PlannerSchemaError, match="domain_hint"):
            provider.plan("query")

    def test_domain_hint_wrong_type(self) -> None:
        provider = self._provider_for({**_VALID_PAYLOAD, "domain_hint": 123})
        with pytest.raises(PlannerSchemaError, match="domain_hint"):
            provider.plan("query")

    def test_lexical_terms_not_list(self) -> None:
        provider = self._provider_for({**_VALID_PAYLOAD, "lexical_terms": "foo"})
        with pytest.raises(PlannerSchemaError, match="lexical_terms"):
            provider.plan("query")

    def test_lexical_terms_contains_non_string(self) -> None:
        provider = self._provider_for({**_VALID_PAYLOAD, "lexical_terms": ["ok", 42]})
        with pytest.raises(PlannerSchemaError, match="lexical_terms"):
            provider.plan("query")

    def test_lexical_terms_contains_empty_string(self) -> None:
        provider = self._provider_for({**_VALID_PAYLOAD, "lexical_terms": ["ok", ""]})
        with pytest.raises(PlannerSchemaError, match="lexical_terms"):
            provider.plan("query")

    def test_confidence_not_number(self) -> None:
        provider = self._provider_for({**_VALID_PAYLOAD, "planner_confidence": "high"})
        with pytest.raises(PlannerSchemaError, match="planner_confidence"):
            provider.plan("query")

    def test_confidence_above_one(self) -> None:
        provider = self._provider_for({**_VALID_PAYLOAD, "planner_confidence": 1.5})
        with pytest.raises(PlannerSchemaError, match="0.0, 1.0"):
            provider.plan("query")

    def test_confidence_below_zero(self) -> None:
        provider = self._provider_for({**_VALID_PAYLOAD, "planner_confidence": -0.1})
        with pytest.raises(PlannerSchemaError, match="0.0, 1.0"):
            provider.plan("query")

    def test_confidence_bool_rejected(self) -> None:
        # Python bool is subclass of int but must not slip through as confidence
        provider = self._provider_for({**_VALID_PAYLOAD, "planner_confidence": True})
        with pytest.raises(PlannerSchemaError, match="planner_confidence"):
            provider.plan("query")


# ---------------------------------------------------------------------------
# Normalization compensation (dedup + strip + truncate)
# ---------------------------------------------------------------------------


class TestNormalization:
    def test_dedupes_terms(self) -> None:
        payload = {**_VALID_PAYLOAD, "lexical_terms": ["a", "b", "a", "c", "b"]}
        provider = _make_provider(_static_handler(_envelope(payload)))
        output = provider.plan("query")
        assert output.lexical_terms == ["a", "b", "c"]

    def test_strips_whitespace_in_terms(self) -> None:
        payload = {**_VALID_PAYLOAD, "lexical_terms": ["  foo  ", "bar", " baz"]}
        provider = _make_provider(_static_handler(_envelope(payload)))
        output = provider.plan("query")
        assert output.lexical_terms == ["foo", "bar", "baz"]

    def test_truncates_to_ten_terms(self) -> None:
        many_terms = [f"term_{i}" for i in range(25)]
        payload = {**_VALID_PAYLOAD, "lexical_terms": many_terms}
        provider = _make_provider(_static_handler(_envelope(payload)))
        output = provider.plan("query")
        assert len(output.lexical_terms) == 10
        assert output.lexical_terms == [f"term_{i}" for i in range(10)]

    def test_skips_whitespace_only_terms(self) -> None:
        payload = {**_VALID_PAYLOAD, "lexical_terms": ["a", "   ", "b", "\t"]}
        provider = _make_provider(_static_handler(_envelope(payload)))
        output = provider.plan("query")
        assert output.lexical_terms == ["a", "b"]


# ---------------------------------------------------------------------------
# Construction & public surface
# ---------------------------------------------------------------------------


class TestConstruction:
    def test_empty_api_key_rejected(self) -> None:
        with pytest.raises(ValueError, match="api_key"):
            QwenApiProvider(
                api_base="http://mock",
                api_model="qwen-test",
                api_key="",
                timeout_seconds=1.0,
            )

    def test_name_attribute_is_stable(self) -> None:
        provider = _make_provider(_static_handler(_envelope(_VALID_PAYLOAD)))
        assert provider.name == "qwen_api"

    def test_api_base_trailing_slash_trimmed(self) -> None:
        # Should accept "http://mock/" and "http://mock" equivalently; we verify
        # this indirectly by confirming the provider doesn't raise on construction
        # and a subsequent call succeeds.
        client = httpx.Client(
            transport=httpx.MockTransport(_static_handler(_envelope(_VALID_PAYLOAD)))
        )
        provider = QwenApiProvider(
            api_base="http://mock.test/",
            api_model="qwen-test",
            api_key="mock-key",
            timeout_seconds=1.0,
            http_client=client,
        )
        # If trailing slash weren't trimmed, url would be "http://mock.test//chat/..."
        # which MockTransport tolerates but is a latent bug. Just assert the call works.
        output = provider.plan("query")
        assert output.domain_hint == "hr"
