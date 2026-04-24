from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class FreshnessResult:
    status: str
    fresh_until: str | None
    stale_after: str | None

    @property
    def is_fresh(self) -> bool:
        return self.status == "fresh"

    @property
    def is_warning(self) -> bool:
        return self.status == "warning"

    @property
    def is_stale(self) -> bool:
        return self.status == "stale"
