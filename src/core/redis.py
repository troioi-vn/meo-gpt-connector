import redis.asyncio as aioredis

from src.core.config import get_settings

_client: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    global _client
    if _client is None:
        settings = get_settings()
        _client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    return _client


async def set_with_ttl(key: str, value: str, ttl: int) -> None:
    """Store a key with an expiry (seconds)."""
    r = await get_redis()
    await r.set(key, value, ex=ttl)


async def get(key: str) -> str | None:
    """Retrieve a key's value, or None if missing/expired."""
    r = await get_redis()
    return await r.get(key)  # type: ignore[no-any-return]


async def delete(key: str) -> None:
    """Delete a key (no-op if already gone)."""
    r = await get_redis()
    await r.delete(key)


async def get_and_delete(key: str) -> str | None:
    """Atomically GET and DELETE a key.

    Uses Redis GETDEL (single command) to prevent auth-code replay — no window
    exists between the read and the delete where a second request could steal
    the same code.
    """
    r = await get_redis()
    return await r.getdel(key)  # type: ignore[no-any-return]


async def incr_with_expiry(key: str, ttl: int) -> int:
    """Increment a counter and set TTL on first increment. Returns the new count.

    Used for fixed-window rate limiting. The TTL is only set when the key is
    created (count == 1), so the window resets naturally after expiry.
    """
    r = await get_redis()
    count = await r.incr(key)
    if count == 1:
        await r.expire(key, ttl)
    return count  # type: ignore[no-any-return]


async def blacklist_jti(jti: str, ttl: int) -> None:
    """Add a JWT ID to the revocation blacklist with the given TTL (seconds)."""
    r = await get_redis()
    await r.set(f"jwt:bl:{jti}", "1", ex=ttl)


async def is_jti_blacklisted(jti: str) -> bool:
    """Return True if this JWT ID has been revoked."""
    r = await get_redis()
    return bool(await r.exists(f"jwt:bl:{jti}"))
