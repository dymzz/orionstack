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

TEST_TMP_ROOT = BACKEND_ROOT.parent / f"pytest-cache-files-{uuid.uuid4().hex}"
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
    # that too instead of silently skipping it.
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
    prefix = (name or "test")[:80]
    path = TEST_TMP_ROOT / f"{prefix}-{uuid.uuid4().hex[:8]}"
    path.mkdir(parents=True, exist_ok=False)
    try:
        yield path
    finally:
        if path.resolve().is_relative_to(TEST_TMP_ROOT.resolve()):
            shutil.rmtree(path, ignore_errors=True)


def pytest_sessionfinish() -> None:
    if TEST_TMP_ROOT.resolve().is_relative_to(BACKEND_ROOT.parent.resolve()):
        shutil.rmtree(TEST_TMP_ROOT, ignore_errors=True)


@pytest.fixture(autouse=True)
def isolate_runtime_storage(tmp_path: Path, monkeypatch) -> None:
    from app.api.routes import chat, documents, extraction
    from app.storage.repositories import extracted_faq_repo as extracted_storage
    from app.storage.repositories.base_repo import JsonlLock
    from app.storage.repositories.chunk_repo import ChunkRepository
    from app.storage.repositories.extraction_candidate_repo import ExtractionCandidateRepo
    from app.storage.repositories.source_record_repo import SourceRecordRepo

    create_chunk_repository = ChunkRepository.__init__
    def isolated_chunk_repository(repository, path=None):
        create_chunk_repository(repository, path=path or tmp_path / "chunks.jsonl")
    monkeypatch.setattr(ChunkRepository, "__init__", isolated_chunk_repository)

    monkeypatch.setattr(extracted_storage, "_STORAGE_DIR", tmp_path / "extracted_faqs")
    extracted_repo = extracted_storage.ExtractedFaqRepo()
    monkeypatch.setattr(extraction, "_extracted_faq_repo", extracted_repo)
    monkeypatch.setattr(chat.service, "_extracted_faq_repo", extracted_repo)
    monkeypatch.setattr(chat.service._ku_repo, "_extracted_faq_repo", extracted_repo)
    monkeypatch.setattr(chat.service._retriever, "_extracted_faq_repo", extracted_repo)
    source_repo = SourceRecordRepo(storage_dir=tmp_path / "source_records")
    monkeypatch.setattr(chat, "source_record_repository", source_repo)
    monkeypatch.setattr(extraction, "_source_record_repo", source_repo)
    monkeypatch.setattr(
        extraction, "_candidate_repo", ExtractionCandidateRepo(storage_dir=tmp_path / "candidates")
    )

    for repository, filename in (
        (chat.chat_record_repository, "chat_records.jsonl"),
        (chat.feedback_repository, "feedback.jsonl"),
        (chat.retrieval_trace_repository, "traces.jsonl"),
        (chat.hard_cases_repository, "hard_cases.jsonl"),
        (chat.service._chunk_repo, "chunks.jsonl"),
        (documents.service._chunk_repository, "chunks.jsonl"),
    ):
        path = tmp_path / filename
        monkeypatch.setattr(repository, "_path", path)
        monkeypatch.setattr(repository, "_lock", JsonlLock(path))
    document_repo = documents.service._repository
    monkeypatch.setattr(document_repo, "_meta_path", tmp_path / "documents.jsonl")
    monkeypatch.setattr(document_repo, "_upload_dir", tmp_path / "uploads")
    monkeypatch.setattr(document_repo, "_lock", JsonlLock(document_repo._meta_path))


@pytest.fixture
def auth_headers() -> dict[str, str]:
    from app.api.auth import create_token
    from fastapi.testclient import TestClient
    from main import app

    client = TestClient(app)
    login = client.post("/api/v1/auth/login", json={"username": "test", "password": "test"})
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_headers() -> dict[str, str]:
    from fastapi.testclient import TestClient
    from main import app

    client = TestClient(app)
    login = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin"})
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
