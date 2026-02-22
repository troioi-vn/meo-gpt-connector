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


async def get_and_delete(key: str) -> str | None:
    """Atomically GET and DELETE a key.

    Uses Redis GETDEL (single command) to prevent auth-code replay — no window
    exists between the read and the delete where a second request could steal
    the same code.
    """
    r = await get_redis()
    return await r.getdel(key)
