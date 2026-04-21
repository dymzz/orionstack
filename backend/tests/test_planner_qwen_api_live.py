"""Live smoke test against real DashScope Qwen API.

Runs the 20-query smoke battery from docs/2_8_smoke_results.md §2 against a
real Qwen endpoint and asserts per-contract expectations derived from
docs/2_6_planner_quality_review.md §5.

Scope:
- Only tests the **planner layer** (QwenApiProvider.plan()). Does NOT touch
  Elasticsearch, ChatService, or FastAPI. Retrieval is a separate concern.
- This is the sole real-signal test for "Qwen in this FAQ scenario meets
  planner contracts" — docs/2_8 §7.3 activity smoke.

Execution:
- Requires `DASHSCOPE_API_KEY` (or `QWEN_API_KEY`) environment variable.
- Without it, the entire module is skipped — safe to include in default
  pytest runs.
- Makes ~19 real API calls (~30-60s total depending on network). Not
  suitable for CI loops; run explicitly:

      uv run python -m pytest backend/tests/test_planner_qwen_api_live.py -v

Output:
- Per-case PASS/FAIL in pytest log with detailed assertion messages on
  failure (showing Qwen's actual PlannerOutput).
- Module finalizer writes a JSON snapshot of all results to
  `docs/2_8_smoke_live_results__{tag}__{model}.json`, where `tag` is
  `cloud` / `local` / `other` derived from ``ORIONSTACK_QWEN_API_BASE``
  and `model` is the sanitized ``ORIONSTACK_QWEN_API_MODEL``. This lets
  cloud (DashScope qwen-plus) and local (llama-server Qwen3-*) runs
  coexist as separate snapshots for side-by-side comparison. The baseline
  cloud result is checked in at
  `docs/2_8_smoke_live_results__cloud__qwen-plus.json`.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

# Mark every test in this module as `live` so the default `pytest` run skips
# them unless the user explicitly passes `-m live` or this file's path.
pytestmark = pytest.mark.live

# ---------------------------------------------------------------------------
# Module-level skip if no API key
# ---------------------------------------------------------------------------

_API_KEY = os.environ.get("DASHSCOPE_API_KEY") or os.environ.get("QWEN_API_KEY")
if not _API_KEY:
    pytest.skip(
        "DASHSCOPE_API_KEY / QWEN_API_KEY not set; skipping live Qwen smoke.",
        allow_module_level=True,
    )

from app.config.settings import Settings  # noqa: E402
from app.query.providers import QwenApiProvider  # noqa: E402
from app.query.providers.errors import PlannerProviderError  # noqa: E402
from app.query.query_planner import PlannerOutput, QueryPlanner  # noqa: E402


# ---------------------------------------------------------------------------
# Smoke case spec (dataclass with ANY sentinels for optional checks)
# ---------------------------------------------------------------------------


class _Any:
    """Sentinel: do not check this field."""

    def __repr__(self) -> str:  # pragma: no cover
        return "<ANY>"


ANY: Any = _Any()


@dataclass
class SmokeCase:
    case_id: str
    query: str
    # domain_hint: ANY = skip check, None = must be null, str = must equal
    expected_domain: Any = ANY
    # confidence bounds; None = no bound
    min_confidence: float | None = None
    max_confidence: float | None = None
    # normalization expectation; ANY = skip, str = must equal
    expected_normalized: Any = ANY
    # expected substrings that must be COVERED by at least one lexical term.
    # Semantics: for each entry `s`, at least one term `t` in output.lexical_terms
    # must satisfy `s in t` (so a richer compound like "请假审批进度" satisfies
    # a required "请假审批"). This checks semantic coverage without forcing
    # Qwen to emit exactly the same tokens the test author imagined.
    must_contain_terms: list[str] = field(default_factory=list)
    # terms that must NOT appear in lexical_terms (character fragments etc.)
    # Strict literal check — any exact-equality match is a violation.
    must_not_contain_terms: list[str] = field(default_factory=list)
    # free-form note for the summary log
    note: str = ""


# ---------------------------------------------------------------------------
# The 20-query battery (mirrors docs/2_8_smoke_results.md §2)
# E2 is dropped as duplicate of A2. E3 (cache stability) lives in its own test.
# ---------------------------------------------------------------------------


BATTERY: list[SmokeCase] = [
    # --- A. domain_hint narrowing (2_6 §5.1) ---
    SmokeCase(
        "A1", "系统权限",
        expected_domain="it", min_confidence=0.60,
        must_contain_terms=["系统权限"],
        must_not_contain_terms=["统权"],
        note="IT-exclusive short query",
    ),
    SmokeCase(
        "A2", "门禁权限怎么申请",
        expected_domain="admin", min_confidence=0.70,
        must_contain_terms=["门禁权限"],
        must_not_contain_terms=["禁权", "限怎", "怎么"],
        note="admin-exclusive specific query",
    ),
    SmokeCase(
        "A3", "请假审批进度在哪里查看",
        expected_domain="hr", min_confidence=0.70,
        must_contain_terms=["请假审批"],
        must_not_contain_terms=["假审", "批进"],
        note="hr-exclusive specific query; canonical §5.2 fragment test",
    ),
    SmokeCase(
        "A4", "报销流程",
        expected_domain="finance", min_confidence=0.55,
        must_contain_terms=["报销"],
        note="finance-exclusive short query",
    ),
    SmokeCase(
        "A5", "怎么提交申请",
        expected_domain=None,  # must be null — cross-domain shared tokens
        max_confidence=0.70,
        note="cross-domain shared words MUST NOT narrow",
    ),

    # --- B. lexical_terms quality (2_6 §5.2) ---
    SmokeCase(
        "B1", "请假审批进度",
        expected_domain="hr",
        must_contain_terms=["请假审批"],
        must_not_contain_terms=["假审", "批进"],
    ),
    SmokeCase(
        "B2", "VPN无法连接怎么办",
        expected_domain="it",
        must_contain_terms=["VPN"],
    ),
    SmokeCase(
        "B3", "邮箱签名怎么修改",
        expected_domain="it",
        must_contain_terms=["邮箱签名"],
        must_not_contain_terms=["箱签"],
    ),
    SmokeCase(
        "B4", "报销单据怎么提交",
        expected_domain="finance",
        must_contain_terms=["报销"],
        must_not_contain_terms=["销单"],
    ),

    # --- C. confidence calibration (2_6 §5.3) ---
    SmokeCase(
        "C1", "如何申请年假",
        expected_domain="hr", min_confidence=0.80,
        must_contain_terms=["申请年假"],
        note="specific query must score high",
    ),
    SmokeCase(
        "C2", "请假",
        expected_domain="hr", min_confidence=0.30, max_confidence=0.75,
        note="pan query — moderate confidence band",
    ),
    SmokeCase(
        "C3", "生产变更",
        expected_domain="ops",
        min_confidence=0.60,
        note=(
            "ops-domain specific term (production change management). "
            "Originally in hard_cases as retrieval negative sample — but the "
            "retrieval failure was a corpus gap (no ops FAQ indexed), not a "
            "planner ambiguity. Planner correctly narrows to ops."
        ),
    ),
    SmokeCase(
        "C4", "生产变更需要怎么申请",
        expected_domain="ops",
        min_confidence=0.60,
        note="expanded ops query; same rationale as C3",
    ),
    SmokeCase(
        "C5", "xxyyzz乱码输入asdfq",
        max_confidence=0.35,
        note="nonsense must be below route_confidence_threshold",
    ),

    # --- D. normalization (2_6 §5.4) ---
    SmokeCase(
        "D1", "请假？",
        expected_normalized="请假?",
        note="fullwidth punct → ASCII",
    ),
    SmokeCase(
        "D2", "HR  FAQ",
        expected_normalized="hr faq",
        note="case lowered, multiple whitespace collapsed",
    ),
    SmokeCase(
        "D3", "如何上传文档？",
        expected_normalized="如何上传文档?",
    ),

    # --- E. Symmetric contamination cross-domain (2_6 §5.1 + §5.5) ---
    SmokeCase(
        "E1", "如何申请系统权限开通",
        expected_domain="it", min_confidence=0.80,
        must_contain_terms=["系统权限"],
        note="symmetric contamination reverse of A2; should hit IT not admin",
    ),
]


# ---------------------------------------------------------------------------
# Shared provider + results recorder
# ---------------------------------------------------------------------------


_RESULTS: dict[str, dict[str, Any]] = {}


@pytest.fixture(scope="module")
def qwen_provider() -> QwenApiProvider:
    """Construct a real QwenApiProvider from current Settings + env."""
    s = Settings()
    return QwenApiProvider(
        api_base=s.qwen_api_base,
        api_model=s.qwen_api_model,
        api_key=_API_KEY,
        timeout_seconds=s.planner_timeout_seconds,
    )


def _derive_backend_tag(api_base: str) -> str:
    """Classify the API endpoint so cloud vs local runs produce distinct
    result files. See module docstring for the naming convention."""
    base = api_base.lower()
    if "dashscope" in base or "aliyuncs" in base:
        return "cloud"
    if "127.0.0.1" in base or "localhost" in base or "0.0.0.0" in base:
        return "local"
    return "other"


def _slugify_model(api_model: str) -> str:
    """Turn an arbitrary model id into a filesystem-safe lowercase slug."""
    slug = api_model.lower()
    # Keep [a-z0-9._-], collapse anything else (including path separators) to '-'
    slug = re.sub(r"[^a-z0-9._-]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or "unknown"


def _results_output_path(repo_root: Path, api_base: str, api_model: str) -> Path:
    tag = _derive_backend_tag(api_base)
    slug = _slugify_model(api_model)
    return repo_root / "docs" / f"2_8_smoke_live_results__{tag}__{slug}.json"


@pytest.fixture(scope="module", autouse=True)
def _results_dumper():
    """Dump all recorded smoke results to a per-backend JSON snapshot so the
    file name reflects which LLM was actually tested. See module docstring
    for the naming convention."""
    _RESULTS.clear()
    yield
    if not _RESULTS:
        return

    # Locate docs/ relative to this test file
    here = Path(__file__).resolve()
    repo_root = here.parents[2]  # backend/tests/<file> → repo root
    settings = Settings()
    out_path = _results_output_path(
        repo_root, settings.qwen_api_base, settings.qwen_api_model
    )
    payload = {
        "backend_tag": _derive_backend_tag(settings.qwen_api_base),
        "api_base": settings.qwen_api_base,
        "api_model": settings.qwen_api_model,
        "total_cases": len(_RESULTS),
        "passed": sum(1 for r in _RESULTS.values() if not r.get("failures")),
        "failed": sum(1 for r in _RESULTS.values() if r.get("failures")),
        "results": _RESULTS,
    }
    out_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    # Print a compact summary to pytest stdout
    print(f"\n[smoke] wrote {out_path}")
    print(f"[smoke] {payload['passed']}/{payload['total_cases']} contract-clean, "
          f"{payload['failed']} with at least one failure")


# ---------------------------------------------------------------------------
# Per-case parametrized test
# ---------------------------------------------------------------------------


def _check_case(case: SmokeCase, output: PlannerOutput) -> list[str]:
    """Return list of contract violation messages; empty list = all pass."""
    failures: list[str] = []

    # domain_hint
    if case.expected_domain is not ANY:
        if case.expected_domain is None:
            if output.domain_hint is not None:
                failures.append(
                    f"domain_hint expected null, got {output.domain_hint!r}"
                )
        elif case.expected_domain != output.domain_hint:
            failures.append(
                f"domain_hint expected {case.expected_domain!r}, "
                f"got {output.domain_hint!r}"
            )

    # confidence bounds
    if case.min_confidence is not None and output.planner_confidence < case.min_confidence:
        failures.append(
            f"planner_confidence {output.planner_confidence:.3f} "
            f"< min {case.min_confidence:.2f}"
        )
    if case.max_confidence is not None and output.planner_confidence > case.max_confidence:
        failures.append(
            f"planner_confidence {output.planner_confidence:.3f} "
            f"> max {case.max_confidence:.2f}"
        )

    # normalized_query
    if case.expected_normalized is not ANY:
        if output.normalized_query != case.expected_normalized:
            failures.append(
                f"normalized_query expected {case.expected_normalized!r}, "
                f"got {output.normalized_query!r}"
            )

    # lexical_terms must cover (substring, not literal equality)
    for required in case.must_contain_terms:
        if not any(required in term for term in output.lexical_terms):
            failures.append(
                f"lexical_terms missing coverage for {required!r} "
                f"(no term contains this substring; got {output.lexical_terms})"
            )

    # lexical_terms must NOT contain (character fragments etc.)
    for forbidden in case.must_not_contain_terms:
        if forbidden in output.lexical_terms:
            failures.append(
                f"lexical_terms contains forbidden fragment {forbidden!r} "
                f"(got {output.lexical_terms})"
            )

    return failures


@pytest.mark.parametrize("case", BATTERY, ids=lambda c: c.case_id)
def test_smoke_case(qwen_provider: QwenApiProvider, case: SmokeCase) -> None:
    try:
        output = qwen_provider.plan(case.query)
    except PlannerProviderError as exc:
        # Record the failure and fail loudly — Qwen hard failures matter.
        _RESULTS[case.case_id] = {
            "query": case.query,
            "note": case.note,
            "error": f"{type(exc).__name__}: {exc}",
            "failures": ["provider raised exception"],
        }
        pytest.fail(
            f"[{case.case_id}] {case.query!r} — provider raised "
            f"{type(exc).__name__}: {exc}"
        )

    failures = _check_case(case, output)
    _RESULTS[case.case_id] = {
        "query": case.query,
        "note": case.note,
        "normalized_query": output.normalized_query,
        "domain_hint": output.domain_hint,
        "lexical_terms": output.lexical_terms,
        "planner_confidence": output.planner_confidence,
        "failures": failures,
    }

    if failures:
        detail = "\n  - ".join(failures)
        pytest.fail(
            f"[{case.case_id}] {case.query!r}\n"
            f"  actual: domain={output.domain_hint!r}, "
            f"conf={output.planner_confidence:.3f}, "
            f"terms={output.lexical_terms}, "
            f"norm={output.normalized_query!r}\n"
            f"  failures:\n  - {detail}"
        )


# ---------------------------------------------------------------------------
# E3 cache stability — two identical calls go to Qwen only once
# ---------------------------------------------------------------------------


class _CallCountingProvider:
    """Wraps a real QwenApiProvider, counting plan() invocations."""

    name = "qwen_api"

    def __init__(self, inner: QwenApiProvider) -> None:
        self._inner = inner
        self.call_count = 0

    def plan(self, normalized_query: str) -> PlannerOutput:
        self.call_count += 1
        return self._inner.plan(normalized_query)


def test_e3_cache_suppresses_second_identical_call(qwen_provider: QwenApiProvider) -> None:
    """2_8 §5.2 cache contract: two identical queries in the same process
    hit the provider exactly once."""
    counting = _CallCountingProvider(qwen_provider)
    planner = QueryPlanner(provider="local", model="stub")
    planner._impl = counting  # type: ignore[attr-defined]
    planner._cache = {}  # type: ignore[attr-defined]
    planner._cache_enabled = True  # type: ignore[attr-defined]

    first = planner.plan("系统权限")
    second = planner.plan("系统权限")

    _RESULTS["E3"] = {
        "query": "系统权限 (×2)",
        "note": "cache stability — identical call must not re-invoke provider",
        "call_count": counting.call_count,
        "first_output": {
            "normalized_query": first.normalized_query,
            "domain_hint": first.domain_hint,
            "lexical_terms": first.lexical_terms,
            "planner_confidence": first.planner_confidence,
        },
        "outputs_equal": first == second,
        "failures": [],
    }

    failures = []
    if counting.call_count != 1:
        failures.append(f"expected exactly 1 provider call, got {counting.call_count}")
    if first != second:
        failures.append("second output differs from first (cache should return equal)")

    _RESULTS["E3"]["failures"] = failures

    if failures:
        pytest.fail("[E3] cache stability — " + "; ".join(failures))
