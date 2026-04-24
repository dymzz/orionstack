from __future__ import annotations

from app.sync.freshness_checker import FreshnessResult


def check_freshness(
    fresh_until: str | None,
    stale_after: str | None,
    now_iso: str | None = None,
) -> FreshnessResult:
    if fresh_until is None and stale_after is None:
        return FreshnessResult(status="fresh", fresh_until=None, stale_after=None)

    from datetime import datetime, timezone
    now = datetime.fromisoformat(now_iso) if now_iso else datetime.now(timezone.utc)

    if fresh_until is not None:
        fu = datetime.fromisoformat(fresh_until)
        if now <= fu:
            return FreshnessResult(status="fresh", fresh_until=fresh_until, stale_after=stale_after)

    if stale_after is not None:
        sa = datetime.fromisoformat(stale_after)
        if now <= sa:
            return FreshnessResult(status="warning", fresh_until=fresh_until, stale_after=stale_after)

    return FreshnessResult(status="stale", fresh_until=fresh_until, stale_after=stale_after)
