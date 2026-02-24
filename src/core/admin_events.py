import json
import time

from src.core.redis import get_redis

_KEY = "admin:events"
_MAX = 1000


async def append_event(event: dict) -> None:
    """Append a request event to the admin sorted set. Trims to last 1000."""
    r = await get_redis()
    score = event.get("ts", time.time())
    await r.zadd(_KEY, {json.dumps(event): score})
    await r.zremrangebyrank(_KEY, 0, -(_MAX + 1))


async def get_recent(n: int = 50, errors_only: bool = False) -> list[dict]:
    """Return up to n most-recent events, optionally filtered to status >= 400."""
    r = await get_redis()
    raw = await r.zrevrange(_KEY, 0, n - 1)
    events = [json.loads(e) for e in raw]
    if errors_only:
        events = [e for e in events if e.get("status", 0) >= 400]
    return events


async def get_active_session_count() -> int:
    """Count active oauth:session:* keys in Redis."""
    r = await get_redis()
    keys = await r.keys("oauth:session:*")
    return len(keys)


async def get_total_event_count() -> int:
    """Return total number of stored events."""
    r = await get_redis()
    return await r.zcard(_KEY)
