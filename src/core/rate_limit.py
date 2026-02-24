import uuid

from fastapi import HTTPException

from src.core import redis as redis_store


async def check_rate_limit(key: str, limit: int) -> None:
    """Redis fixed-window rate limiter. Raises HTTP 429 if the key exceeds *limit* requests/min."""
    count = await redis_store.incr_with_expiry(f"rl:{key}", ttl=60)
    if count > limit:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "RATE_LIMIT_EXCEEDED",
                "message": "Too many requests. Please slow down.",
                "fields": [],
                "request_id": f"req_{uuid.uuid4().hex[:12]}",
            },
        )
