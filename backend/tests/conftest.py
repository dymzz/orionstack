from __future__ import annotations

import os
import shutil
import sys
import uuid
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
