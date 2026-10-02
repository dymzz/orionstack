from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any


BASE_STORAGE_DIR = Path(__file__).resolve().parents[1]


class JsonlLock:
    """Cross-platform file-based lock for JSONL repository operations.

    Uses mkdir as an atomic operation on both POSIX and Windows.
    Acquire creates a temporary directory next to the data file;
    release removes it. Safe for single-process deployments where
    concurrent writes may come from overlapping async handlers.
    """

    def __init__(self, storage_path: Path) -> None:
        self._lock_path = storage_path.with_suffix(".lock")

    def __enter__(self) -> "JsonlLock":
        deadline = time.monotonic() + 5.0
        while True:
            try:
                self._lock_path.mkdir(parents=False, exist_ok=False)
                return self
            except FileExistsError:
                if time.monotonic() > deadline:
                    raise TimeoutError(
                        f"Could not acquire lock for {self._lock_path} within 5s"
                    )
                time.sleep(0.01)

    def __exit__(self, *args: Any) -> None:
        try:
            self._lock_path.rmdir()
        except OSError:
            pass