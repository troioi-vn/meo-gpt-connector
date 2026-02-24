from __future__ import annotations
import json
import time
from typing import Any

from src.core.redis import get_redis

_KEY = "admin:events"
_MAX = 1000


def _path(event: dict[str, Any]) -> str:
    return str(event.get("path") or "")


def _is_admin_event(event: dict[str, Any]) -> bool:
    return _path(event).startswith("/admin")


async def append_event(event: dict[str, Any]) -> None:
    """Append a request event to the admin sorted set. Trims to last 1000."""
    r = await get_redis()
    score = event.get("ts", time.time())
    await r.zadd(_KEY, {json.dumps(event): score})
    await r.zremrangebyrank(_KEY, 0, -(_MAX + 1))


async def get_recent(
    n: int = 50,
    errors_only: bool = False,
    skip_admin: bool = False,
    include_paths: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Return recent events with optional filtering.

    Args:
        n: Number of events to return.
        errors_only: Keep only events with status >= 400.
        skip_admin: Exclude /admin* events.
        include_paths: Keep only events where path starts with one of these prefixes.
    """
    r = await get_redis()
    scan_size = n
    if skip_admin or include_paths:
        scan_size = min(_MAX, max(200, n * 8))

    raw = await r.zrevrange(_KEY, 0, scan_size - 1)
    events = [json.loads(e) for e in raw]

    if skip_admin:
        events = [e for e in events if not _is_admin_event(e)]

    if include_paths:
        events = [e for e in events if any(_path(e).startswith(prefix) for prefix in include_paths)]

    if errors_only:
        events = [e for e in events if e.get("status", 0) >= 400]

    return events[:n]


async def get_active_session_count() -> int:
    """Count active oauth:session:* keys in Redis."""
    r = await get_redis()
    keys = await r.keys("oauth:session:*")
    return len(keys)


async def get_total_event_count() -> int:
    """Return total number of stored events."""
    r = await get_redis()
    return await r.zcard(_KEY)  # type: ignore[no-any-return]
