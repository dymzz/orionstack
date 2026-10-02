from __future__ import annotations

from typing import Any


def check_hit_freshness(hit) -> Any | None:
    from app.sync.freshness import check_freshness

    fresh_until = hit.fresh_until if hasattr(hit, "fresh_until") else ""
    stale_after = hit.stale_after if hasattr(hit, "stale_after") else ""
    if not fresh_until and not stale_after:
        return None
    return check_freshness(fresh_until or None, stale_after or None)


def check_item_freshness(item: dict[str, Any]) -> Any | None:
    from app.sync.freshness import check_freshness

    fresh_until = item.get("fresh_until") or ""
    stale_after = item.get("stale_after") or ""
    if not fresh_until and not stale_after:
        return None
    return check_freshness(fresh_until or None, stale_after or None)