"""Small HTTP boundary: bounded inputs, typed failures, and no credential logging."""

import json
from typing import Any

import httpx

from app.knowledge.contracts import AccessContext, EvidenceCandidate


class ProviderError(RuntimeError):
    def __init__(self, provider: str, code: str, status_code: int | None = None) -> None:
        self.provider = provider
        self.code = code
        self.status_code = status_code
        super().__init__(f"{provider}: {code}" + (f" (HTTP {status_code})" if status_code else ""))


def parse_json(value: str | bytes) -> Any:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result = {}
        for key, item in items:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = item
        return result

    def invalid_constant(_: str) -> None:
        raise ValueError("Nonfinite JSON number")

    return json.loads(value, object_pairs_hook=pairs, parse_constant=invalid_constant)


def post_json(provider: str, url: str, key: str, payload: dict[str, Any],
              timeout: float, client: httpx.Client | None = None) -> dict[str, Any]:
    try:
        encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (ValueError, TypeError):
        raise ProviderError(provider, "invalid_request") from None
    if len(encoded) > 200_000:
        raise ProviderError(provider, "input_too_large")
    owned_client = client is None
    http_client = client if client is not None else httpx.Client()
    try:
        response = http_client.post(
            url, content=encoded,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            timeout=timeout, follow_redirects=False,
        )
        if not 200 <= response.status_code < 300:
            raise ProviderError(provider, "http_error", response.status_code)
        if len(response.content) > 1_000_000:
            raise ProviderError(provider, "response_too_large")
        try:
            result = parse_json(response.content)
        except (ValueError, UnicodeError):
            raise ProviderError(provider, "invalid_json") from None
        if not isinstance(result, dict):
            raise ProviderError(provider, "invalid_response")
        return result
    except httpx.TimeoutException:
        raise ProviderError(provider, "timeout") from None
    except httpx.HTTPError:
        raise ProviderError(provider, "transport_error") from None
    finally:
        if owned_client:
            http_client.close()


def authorized_evidence(candidates: tuple[EvidenceCandidate, ...], access: AccessContext) -> None:
    """Defense at the model boundary; database queries must also apply these filters."""
    if len({candidate.evidence_id for candidate in candidates}) != len(candidates):
        raise ValueError("Duplicate evidence ID")
    if any(candidate.tenant_id != access.tenant_id or candidate.access_scope not in access.allowed_scopes
           for candidate in candidates):
        raise PermissionError("Evidence is outside the authenticated principal's scope")
