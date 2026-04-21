from __future__ import annotations

import os
import json
import re
import shutil
import sys
import uuid
from functools import lru_cache
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

# Tests pin their own runtime defaults so project-level production defaults
# can move without silently changing the test baseline.
os.environ.setdefault("ORIONSTACK_SEARCH_BACKEND", "local")
os.environ.setdefault("ORIONSTACK_ENABLE_QUERY_PLANNER", "false")
os.environ.setdefault("ORIONSTACK_ENABLE_FAST_TRACK", "false")

TEST_TMP_ROOT = Path(__file__).resolve().parent / "_tmp"
TEST_TMP_ROOT.mkdir(exist_ok=True)

_JSON_BLOCK_PATTERN = re.compile(r"```json\s*(\[.*?\])\s*```", re.S)
_FAQ_CASE_QUESTIONS = {
    "leave_apply": "如何申请年假？",
    "sick_leave_materials": "病假需要提交什么材料？",
    "leave_progress": "请假审批进度在哪里查看？",
    "attendance_appeal": "考勤异常怎么申诉？",
    "onboarding_day_one": "入职第一天需要办理什么手续？",
    "resignation_process": "离职流程怎么走？",
    "employment_certificate": "在职证明怎么申请？",
    "social_security_start": "社保和公积金从什么时候开始缴纳？",
    "payroll_slip": "工资条在哪里查看？",
    "benefits_info": "公司福利信息在哪里查看？",
    "timeoff_balance": "调休余额在哪里看？",
    "probation_review": "试用期考核结果在哪里确认？",
}


@lru_cache(maxsize=1)
def load_seed_faqs() -> tuple[dict, ...]:
    items: list[dict] = []
    for fixture_items in seed_fixture_items_by_path().values():
        items.extend(fixture_items)
    if not items:
        raise AssertionError("failed to load FAQ seed fixtures")
    return tuple(items)


@lru_cache(maxsize=1)
def fixture_faq_map() -> dict[str, dict]:
    return {item["id"]: item for item in load_seed_faqs()}


@lru_cache(maxsize=1)
def fixture_question_map() -> dict[str, dict]:
    return {item["question"]: item for item in load_seed_faqs()}


def fixture_faq_by_id(faq_id: str) -> dict:
    return fixture_faq_map()[faq_id]


def fixture_faq_by_question(question: str) -> dict:
    return fixture_question_map()[question]


def fixture_case(case_name: str) -> dict:
    return fixture_faq_by_question(_FAQ_CASE_QUESTIONS[case_name])


@lru_cache(maxsize=1)
def seed_fixture_paths() -> tuple[Path, ...]:
    fixture_dir = Path(__file__).resolve().parent / "fixtures"
    paths = tuple(sorted(fixture_dir.glob("domain_*_faq_seed_*.md")))
    if not paths:
        raise AssertionError("failed to locate FAQ seed fixture files")
    return paths


@lru_cache(maxsize=1)
def seed_fixture_items_by_path() -> dict[Path, tuple[dict, ...]]:
    items_by_path: dict[Path, tuple[dict, ...]] = {}
    for fixture_path in seed_fixture_paths():
        text = fixture_path.read_text(encoding="utf-8")
        match = _JSON_BLOCK_PATTERN.search(text)
        if match is None:
            continue
        items_by_path[fixture_path] = tuple(json.loads(match.group(1)))
    if not items_by_path:
        raise AssertionError("failed to parse FAQ seed fixture files")
    return items_by_path


def fixture_path_for_faq_id(faq_id: str) -> Path:
    for fixture_path, items in seed_fixture_items_by_path().items():
        if any(item["id"] == faq_id for item in items):
            return fixture_path
    raise KeyError(faq_id)


def primary_seed_fixture_path() -> Path:
    return seed_fixture_paths()[0]


def pytest_configure(config: pytest.Config) -> None:
    # Opt-in marker for tests that hit real external services (Qwen API, etc.).
    # Default pytest runs skip these; to run them pass `-m live` or the explicit
    # test file path (file-path mode bypasses the default skip).
    config.addinivalue_line(
        "markers",
        "live: opt-in live-API smoke test; requires network + API key",
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    # If the user explicitly asked for `-m live` (or a superset), respect it.
    markexpr = getattr(config.option, "markexpr", "") or ""
    if "live" in markexpr:
        return

    # If the user passed a path that explicitly targets a live test file, honor
    # that too — running `pytest backend/tests/test_planner_qwen_api_live.py`
    # should NOT be silently skipped.
    explicit_args = [str(arg) for arg in config.args]
    if any("_live" in arg for arg in explicit_args):
        return

    skip_live = pytest.mark.skip(
        reason="live test skipped by default — pass `-m live` or the file path to run"
    )
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip_live)


@pytest.fixture
def tmp_path(request: pytest.FixtureRequest) -> Path:
    name = "".join(
        character if character.isalnum() or character in {"-", "_"} else "-"
        for character in request.node.name
    ).strip("-")
    prefix = name or "test"
    path = TEST_TMP_ROOT / f"{prefix}-{uuid.uuid4().hex[:8]}"
    path.mkdir(parents=True, exist_ok=False)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)
