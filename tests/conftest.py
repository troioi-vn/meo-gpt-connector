import pytest
from unittest.mock import patch
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


@pytest.fixture
def client():
    from src.main import app

    # Patch at both levels: FastAPI DI and direct module calls (e.g. in lifespan)
    app.dependency_overrides[get_settings] = lambda: TEST_SETTINGS
    with patch("src.main.get_settings", return_value=TEST_SETTINGS):
        with TestClient(app) as c:
            yield c
    app.dependency_overrides.clear()
