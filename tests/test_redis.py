from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture
async def mock_redis():
    """Inject a mock Redis client directly into the module-level singleton."""
    import src.core.redis as redis_module

    client = AsyncMock()
    client.set = AsyncMock(return_value=True)
    client.getdel = AsyncMock(return_value=None)

    previous = redis_module._client
    redis_module._client = client
    yield client
    redis_module._client = previous


async def test_set_with_ttl_calls_set_with_ex(mock_redis):
    from src.core.redis import set_with_ttl

    await set_with_ttl("auth:code:abc", "payload", 300)
    mock_redis.set.assert_awaited_once_with("auth:code:abc", "payload", ex=300)


async def test_get_and_delete_returns_value(mock_redis):
    from src.core.redis import get_and_delete

    mock_redis.getdel.return_value = "stored-value"
    result = await get_and_delete("auth:code:abc")

    assert result == "stored-value"
    mock_redis.getdel.assert_awaited_once_with("auth:code:abc")


async def test_get_and_delete_returns_none_for_missing_key(mock_redis):
    from src.core.redis import get_and_delete

    mock_redis.getdel.return_value = None
    assert await get_and_delete("nonexistent") is None


async def test_get_and_delete_uses_getdel_not_get_then_del(mock_redis):
    """Ensure atomicity: GETDEL is one command, not GET + DEL."""
    from src.core.redis import get_and_delete

    await get_and_delete("some-key")

    # getdel called once — no separate get/delete
    assert mock_redis.getdel.await_count == 1
    mock_redis.get.assert_not_awaited()
    mock_redis.delete.assert_not_awaited()


async def test_get_redis_initialization():
    import src.core.redis as redis_module
    from unittest.mock import patch
    
    redis_module._client = None
    with patch("src.core.redis.aioredis.from_url") as mock_from_url:
        mock_from_url.return_value = AsyncMock()
        client = await redis_module.get_redis()
        assert client is not None
        mock_from_url.assert_called_once()
    # Reset globally
    redis_module._client = None

