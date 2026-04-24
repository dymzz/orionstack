"""OpenAI-compatible planner provider.

This implementation speaks the generic Chat Completions contract and can be
used against multiple backends. The legacy ``QwenApiProvider`` remains as a
compatibility wrapper around this class.
"""

from __future__ import annotations

import json
import re
from typing import Any

import httpx

from app.query.providers.errors import (
    PlannerHttpError,
    PlannerParseError,
    PlannerSchemaError,
    PlannerTimeoutError,
)
from app.query.query_planner import PlannerOutput


_DOMAIN_ENUM: frozenset[str] = frozenset(
    {"hr", "finance", "admin", "it", "ops", "legal", "product", "sales"}
)
_LEXICAL_TERMS_MAX: int = 10
_ASCII_TERM_RE = re.compile(r"[A-Za-z][A-Za-z0-9-]*")


_SYSTEM_PROMPT: str = """\
你是一个查询理解组件，任务是把用户的中文自然语言查询解析为结构化的 planner 输出。

已知的业务领域（business_domain）枚举：
- hr: 人事、请假、考勤、薪酬、合同、入离职
- finance: 财务、报销、付款、预算、发票
- admin: 行政、门禁、办公用品、会议室、差旅预订
- it: 技术支持、账号、系统登录、权限、设备
- ops: 运营、生产变更、值班、事件处理
- legal: 法务、合同审批、印章、合规、保密协议
- product: 产品、需求、版本、缺陷、发布
- sales: 销售、报价、客户、商机、合同模板

输出要求（严格 JSON，不要任何前后缀文字）：
{
  "normalized_query": string,
  "domain_hint": string | null,
  "lexical_terms": string[],
  "planner_confidence": number
}

规则：
1. domain_hint 只在查询明确包含单一领域专属词时给出；跨域共享词（"申请"、"审批"、"提交"）必须返回 null
2. lexical_terms 必须是完整语义的词或短语，不能是字符碎片（如"假审"、"批进"是禁止的），最多 10 个
3. normalized_query 做以下规范化：全角标点转半角、英文转小写、连续空白压缩为单个
4. planner_confidence 反映"本条解析的可信度"：具体完整的问句高（0.8+），模糊泛问低（0.3-0.5），乱码或多意图混合低于 0.15

示例：

输入：如何申请年假？
输出：{"normalized_query":"如何申请年假?","domain_hint":"hr","lexical_terms":["申请年假","年假","申请"],"planner_confidence":0.92}

输入：怎么提交申请
输出：{"normalized_query":"怎么提交申请","domain_hint":null,"lexical_terms":["提交申请","申请"],"planner_confidence":0.45}

输入：请假
输出：{"normalized_query":"请假","domain_hint":"hr","lexical_terms":["请假"],"planner_confidence":0.38}

输入：xxyyzz 乱码输入 asdfq
输出：{"normalized_query":"xxyyzz 乱码输入 asdfq","domain_hint":null,"lexical_terms":["乱码输入"],"planner_confidence":0.08}
"""


class OpenAICompatiblePlannerProvider:
    """Calls an OpenAI-compatible /chat/completions endpoint."""

    def __init__(
        self,
        *,
        api_base: str,
        api_model: str,
        api_key: str,
        timeout_seconds: float,
        provider_name: str = "openai_compatible",
        http_client: httpx.Client | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("api_key must be non-empty for OpenAICompatiblePlannerProvider")
        self.name: str = provider_name
        self._api_base: str = api_base.rstrip("/")
        self._api_model: str = api_model
        self._api_key: str = api_key
        self._timeout: float = timeout_seconds
        self._http_client: httpx.Client | None = http_client

    def plan(self, normalized_query: str) -> PlannerOutput:
        envelope = self._call_api(normalized_query)
        return self._parse_response(envelope, source_query=normalized_query)

    def _call_api(self, query: str) -> dict[str, Any]:
        url = f"{self._api_base}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._api_model,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": f"查询：{query}"},
            ],
            "temperature": 0.0,
            "top_p": 1.0,
            "max_tokens": 1024,
            "response_format": {"type": "json_object"},
        }

        try:
            if self._http_client is not None:
                response = self._http_client.post(
                    url, headers=headers, json=payload, timeout=self._timeout
                )
            else:
                with httpx.Client(timeout=self._timeout) as client:
                    response = client.post(url, headers=headers, json=payload)
        except httpx.TimeoutException as exc:
            raise PlannerTimeoutError(f"{self.name} timeout: {exc}") from exc
        except httpx.HTTPError as exc:
            raise PlannerHttpError(f"{self.name} connection error: {exc}") from exc

        if response.status_code != 200:
            snippet = response.text[:200] if response.text else ""
            raise PlannerHttpError(
                f"{self.name} status={response.status_code} body={snippet!r}"
            )

        try:
            return response.json()
        except ValueError as exc:
            raise PlannerParseError(
                f"{self.name} response body is not json: {exc}"
            ) from exc

    def _parse_response(
        self, envelope: dict[str, Any], *, source_query: str
    ) -> PlannerOutput:
        content = self._extract_content(envelope)
        payload = self._parse_content_json(content)
        self._validate_schema(payload)

        normalized_query = payload["normalized_query"]
        domain_hint = payload.get("domain_hint")
        lexical_terms = self._dedupe_and_truncate(
            self._restore_ascii_casing_from_query(
                payload["lexical_terms"], source_query=source_query
            )
        )
        confidence = float(payload["planner_confidence"])

        return PlannerOutput(
            normalized_query=normalized_query,
            domain_hint=domain_hint,
            lexical_terms=lexical_terms,
            planner_confidence=confidence,
        )

    @staticmethod
    def _extract_content(envelope: dict[str, Any]) -> str:
        try:
            choices = envelope["choices"]
            content = choices[0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise PlannerParseError(
                f"missing choices[0].message.content in envelope: {exc}"
            ) from exc
        if not isinstance(content, str):
            raise PlannerParseError(
                f"choices[0].message.content is not str: {type(content).__name__}"
            )
        return content

    @staticmethod
    def _sanitize_content(content: str) -> str:
        stripped = re.sub(
            r"<think\b[^>]*>.*?</think>",
            "",
            content,
            flags=re.DOTALL | re.IGNORECASE,
        )

        if re.search(r"<think\b", stripped, flags=re.IGNORECASE):
            raise PlannerParseError(
                "llm response contains unclosed <think> block (reasoning "
                "model ran out of n_predict budget before emitting JSON); "
                "increase llama-server --n-predict or disable thinking mode"
            )

        stripped = stripped.strip()
        if stripped.startswith("```"):
            stripped = re.sub(r"^```(?:json|JSON)?\s*\n?", "", stripped)
            stripped = re.sub(r"\n?\s*```\s*$", "", stripped)

        return stripped.strip()

    @classmethod
    def _parse_content_json(cls, content: str) -> Any:
        cleaned = cls._sanitize_content(content)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise PlannerParseError(
                f"message content is not valid json: {exc}"
            ) from exc

    @staticmethod
    def _validate_schema(payload: Any) -> None:
        if not isinstance(payload, dict):
            raise PlannerSchemaError(
                f"content must be a json object, got {type(payload).__name__}"
            )

        nq = payload.get("normalized_query")
        if not isinstance(nq, str):
            raise PlannerSchemaError(
                f"normalized_query must be str, got {type(nq).__name__}"
            )

        dh = payload.get("domain_hint")
        if dh is not None:
            if not isinstance(dh, str) or dh not in _DOMAIN_ENUM:
                raise PlannerSchemaError(
                    f"domain_hint must be null or one of {sorted(_DOMAIN_ENUM)}, "
                    f"got {dh!r}"
                )

        lt = payload.get("lexical_terms")
        if not isinstance(lt, list):
            raise PlannerSchemaError(
                f"lexical_terms must be list, got {type(lt).__name__}"
            )
        for index, term in enumerate(lt):
            if not isinstance(term, str) or not term:
                raise PlannerSchemaError(
                    f"lexical_terms[{index}] must be non-empty str, got {term!r}"
                )

        pc = payload.get("planner_confidence")
        if not isinstance(pc, (int, float)) or isinstance(pc, bool):
            raise PlannerSchemaError(
                f"planner_confidence must be number, got {type(pc).__name__}"
            )
        if not (0.0 <= float(pc) <= 1.0):
            raise PlannerSchemaError(
                f"planner_confidence must be within [0.0, 1.0], got {pc!r}"
            )

    @staticmethod
    def _dedupe_and_truncate(terms: list[str]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for term in terms:
            stripped = term.strip()
            if not stripped or stripped in seen:
                continue
            result.append(stripped)
            seen.add(stripped)
            if len(result) >= _LEXICAL_TERMS_MAX:
                break
        return result

    @staticmethod
    def _restore_ascii_casing_from_query(
        terms: list[str], *, source_query: str
    ) -> list[str]:
        query_tokens = _ASCII_TERM_RE.findall(source_query)
        if not query_tokens:
            return terms

        restored_terms: list[str] = []
        for term in terms:
            restored = term
            for query_token in sorted(query_tokens, key=len, reverse=True):
                restored = re.sub(
                    re.escape(query_token),
                    query_token,
                    restored,
                    flags=re.IGNORECASE,
                )
            restored_terms.append(restored)
        return restored_terms

