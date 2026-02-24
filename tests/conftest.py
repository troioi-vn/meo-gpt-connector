import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from src.core.config import Settings, get_settings

TEST_SETTINGS = Settings(
    MAIN_APP_URL="http://test-main-app",
    CONNECTOR_API_KEY="test-api-key",
    OAUTH_CLIENT_ID="meo-gpt",
    OAUTH_CLIENT_SECRET="test-client-secret",
    JWT_SECRET="test-jwt-secret-that-is-long-enough",
    ENCRYPTION_KEY="0" * 64,  # 32 zero bytes in hex
    HMAC_SHARED_SECRET="test-hmac-secret",
    REDIS_URL="redis://localhost:6379",
    LOG_LEVEL="debug",
    ENVIRONMENT="test",
)


@pytest.fixture(autouse=True)
def _clear_pet_types_cache():
    """Reset the module-level pet types cache before each test to prevent bleed-over."""
    import src.services.main_app as _svc

    _svc._PET_TYPES_BY_NAME.clear()
    _svc._PET_TYPES_BY_ID.clear()
    yield
    _svc._PET_TYPES_BY_NAME.clear()
    _svc._PET_TYPES_BY_ID.clear()


@pytest.fixture(autouse=True)
def _mock_redis_hardening():
    """Mock rate-limit and blacklist Redis calls so tests don't need a live Redis.

    By default: tokens are never blacklisted, requests are never rate-limited.
    Override these in specific tests that exercise those code paths.
    """
    with (
        patch("src.core.redis.is_jti_blacklisted", new=AsyncMock(return_value=False)),
        patch("src.core.redis.incr_with_expiry", new=AsyncMock(return_value=1)),
        patch("src.core.redis.blacklist_jti", new=AsyncMock()),
    ):
        yield


@pytest.fixture
def client():
    from src.main import app

    # Patch at both levels: FastAPI DI and direct module calls (e.g. in lifespan)
    app.dependency_overrides[get_settings] = lambda: TEST_SETTINGS
    with patch("src.main.get_settings", return_value=TEST_SETTINGS):
        with TestClient(app) as c:
            yield c
    app.dependency_overrides.clear()
