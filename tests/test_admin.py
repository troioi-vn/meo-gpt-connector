import base64
import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from src.core.config import Settings, get_settings


def _make_admin_settings(**overrides) -> Settings:
    base = dict(
        MAIN_APP_URL="http://test-main-app",
        CONNECTOR_API_KEY="test-api-key",
        OAUTH_CLIENT_ID="meo-gpt",
        OAUTH_CLIENT_SECRET="test-client-secret",
        JWT_SECRET="test-jwt-secret-that-is-long-enough",
        ENCRYPTION_KEY="0" * 64,
        HMAC_SHARED_SECRET="test-hmac-secret",
        REDIS_URL="redis://localhost:6379",
        LOG_LEVEL="debug",
        ENVIRONMENT="test",
        ADMIN_ENABLED=True,
        ADMIN_PASSWORD="testpass",
    )
    base.update(overrides)
    return Settings(**base)


def _basic_header(username: str, password: str) -> dict[str, str]:
    encoded = base64.b64encode(f"{username}:{password}".encode()).decode()
    return {"Authorization": f"Basic {encoded}"}


@pytest.fixture
def admin_client():
    from src.main import app

    settings = _make_admin_settings()
    app.dependency_overrides[get_settings] = lambda: settings
    with patch("src.main.get_settings", return_value=settings):
        with TestClient(app) as c:
            yield c
    app.dependency_overrides.clear()


# ── Disabled admin ────────────────────────────────────────────────────────────

def test_admin_disabled_returns_404(client):
    """When ADMIN_ENABLED=False (default test settings), /admin/ returns 404."""
    from src.main import app

    disabled = _make_admin_settings(ADMIN_ENABLED=False)
    app.dependency_overrides[get_settings] = lambda: disabled
    try:
        with patch("src.main.get_settings", return_value=disabled):
            resp = client.get("/admin/")
        assert resp.status_code == 404
    finally:
        app.dependency_overrides.clear()


# ── Auth enforcement ──────────────────────────────────────────────────────────

def test_admin_no_credentials_returns_401(admin_client):
    resp = admin_client.get("/admin/", auth=None)
    # httpx/TestClient sends no auth header → 401 with WWW-Authenticate
    assert resp.status_code == 401
    assert "WWW-Authenticate" in resp.headers


def test_admin_wrong_password_returns_401(admin_client):
    resp = admin_client.get("/admin/", headers=_basic_header("admin", "wrongpass"))
    assert resp.status_code == 401


def test_admin_wrong_username_returns_401(admin_client):
    resp = admin_client.get("/admin/", headers=_basic_header("notadmin", "testpass"))
    assert resp.status_code == 401


# ── Successful access ─────────────────────────────────────────────────────────

def test_admin_index_renders(admin_client):
    with (
        patch("src.routers.admin.get_recent", new_callable=AsyncMock, return_value=[]),
        patch("src.routers.admin.get_total_event_count", new_callable=AsyncMock, return_value=0),
        patch("src.routers.admin.get_active_session_count", new_callable=AsyncMock, return_value=0),
    ):
        resp = admin_client.get("/admin/", headers=_basic_header("admin", "testpass"))
    assert resp.status_code == 200
    assert "htmx" in resp.text.lower()
    assert "admin/partials/requests" in resp.text
    assert "admin/partials/auth" in resp.text


def test_admin_requests_partial(admin_client):
    events = [
        {"ts": 1700000001, "method": "GET", "path": "/pets", "user_id": 7, "status": 200, "latency_ms": 45},
        {"ts": 1700000002, "method": "POST", "path": "/pets", "user_id": 7, "status": 422, "latency_ms": 12},
    ]
    with patch("src.routers.admin.get_recent", new_callable=AsyncMock, return_value=events):
        resp = admin_client.get("/admin/partials/requests", headers=_basic_header("admin", "testpass"))
    assert resp.status_code == 200
    assert "/pets" in resp.text
    assert "422" in resp.text


def test_admin_errors_partial_shows_only_errors(admin_client):
    errors = [
        {"ts": 1700000003, "method": "GET", "path": "/pets/99", "user_id": None, "status": 404, "latency_ms": 8, "error_code": None},
    ]
    with patch("src.routers.admin.get_recent", new_callable=AsyncMock, return_value=errors):
        resp = admin_client.get("/admin/partials/errors", headers=_basic_header("admin", "testpass"))
    assert resp.status_code == 200
    assert "404" in resp.text


def test_admin_errors_partial_no_errors(admin_client):
    with patch("src.routers.admin.get_recent", new_callable=AsyncMock, return_value=[]):
        resp = admin_client.get("/admin/partials/errors", headers=_basic_header("admin", "testpass"))
    assert resp.status_code == 200
    assert "Meow" in resp.text


def test_admin_auth_partial(admin_client):
    auth_events = [
        {"ts": 1700000003, "method": "POST", "path": "/oauth/token", "user_id": None, "status": 200, "latency_ms": 7, "error_code": None},
    ]
    with patch("src.routers.admin.get_recent", new_callable=AsyncMock, return_value=auth_events):
        resp = admin_client.get("/admin/partials/auth", headers=_basic_header("admin", "testpass"))
    assert resp.status_code == 200
    assert "/oauth/token" in resp.text
    assert "token exchange" in resp.text


def test_admin_stats_partial(admin_client):
    with (
        patch("src.routers.admin.get_total_event_count", new_callable=AsyncMock, return_value=42),
        patch("src.routers.admin.get_active_session_count", new_callable=AsyncMock, return_value=3),
        patch("src.routers.admin.get_recent", new_callable=AsyncMock, return_value=[]),
    ):
        resp = admin_client.get("/admin/partials/stats", headers=_basic_header("admin", "testpass"))
    assert resp.status_code == 200
    assert "42" in resp.text
    assert "3" in resp.text


# ── admin_events unit tests ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_append_and_get_recent():
    mock_redis = AsyncMock()
    mock_redis.zrevrange.return_value = [
        json.dumps({"ts": 1.0, "path": "/pets", "status": 200}),
        json.dumps({"ts": 0.9, "path": "/pets/1", "status": 404}),
    ]
    with patch("src.core.admin_events.get_redis", return_value=mock_redis):
        from src.core.admin_events import get_recent
        events = await get_recent(n=50)
    assert len(events) == 2
    assert events[0]["path"] == "/pets"


@pytest.mark.asyncio
async def test_get_recent_errors_only():
    mock_redis = AsyncMock()
    mock_redis.zrevrange.return_value = [
        json.dumps({"ts": 1.0, "path": "/pets", "status": 200}),
        json.dumps({"ts": 0.9, "path": "/pets/99", "status": 404}),
    ]
    with patch("src.core.admin_events.get_redis", return_value=mock_redis):
        from src.core.admin_events import get_recent
        events = await get_recent(n=50, errors_only=True)
    assert len(events) == 1
    assert events[0]["status"] == 404


@pytest.mark.asyncio
async def test_get_recent_skip_admin():
    mock_redis = AsyncMock()
    mock_redis.zrevrange.return_value = [
        json.dumps({"ts": 1.0, "path": "/admin/partials/stats", "status": 200}),
        json.dumps({"ts": 0.9, "path": "/pets", "status": 200}),
    ]
    with patch("src.core.admin_events.get_redis", return_value=mock_redis):
        from src.core.admin_events import get_recent
        events = await get_recent(n=50, skip_admin=True)
    assert len(events) == 1
    assert events[0]["path"] == "/pets"


@pytest.mark.asyncio
async def test_append_event_zadd_and_trim():
    mock_redis = AsyncMock()
    with patch("src.core.admin_events.get_redis", return_value=mock_redis):
        from src.core.admin_events import append_event
        await append_event({"ts": 1700000000.0, "path": "/test", "status": 200})
    mock_redis.zadd.assert_called_once()
    mock_redis.zremrangebyrank.assert_called_once()
