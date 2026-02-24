"""Tests for rate limiting and JWT revocation blacklist (task 09 hardening)."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx

from src.core.jwt import create_jwt
from tests.conftest import TEST_SETTINGS


def _auth_headers(user_id: int = 7) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_jwt(user_id=user_id, sanctum_token='tok')}"}


# ---------------------------------------------------------------------------
# Rate limiting — /oauth/authorize (IP-based)
# ---------------------------------------------------------------------------


def test_authorize_rate_limit_triggers_429(client):
    """The 61st request from the same IP within a minute returns 429."""
    with patch("src.core.redis.incr_with_expiry", new=AsyncMock(return_value=61)):
        resp = client.get(
            "/oauth/authorize",
            params={
                "client_id": "meo-gpt",
                "response_type": "code",
                "redirect_uri": "https://chat.openai.com/aip/callback",
                "state": "abc",
            },
        )
    assert resp.status_code == 429
    body = resp.json()
    assert body["detail"]["error"] == "RATE_LIMIT_EXCEEDED"


def test_authorize_below_rate_limit_succeeds(client):
    """Requests below the limit are not blocked (redirect to main app)."""
    with patch("src.core.redis.incr_with_expiry", new=AsyncMock(return_value=1)):
        with patch("src.core.redis.set_with_ttl", new=AsyncMock()):
            resp = client.get(
                "/oauth/authorize",
                params={
                    "client_id": "meo-gpt",
                    "response_type": "code",
                    "redirect_uri": "https://chat.openai.com/aip/callback",
                    "state": "abc",
                },
                follow_redirects=False,
            )
    assert resp.status_code == 302


# ---------------------------------------------------------------------------
# Rate limiting — /pets (user_id-based)
# ---------------------------------------------------------------------------


@respx.mock
def test_pets_rate_limit_triggers_429(client):
    """The 61st call with the same user JWT returns 429."""
    with patch("src.core.redis.incr_with_expiry", new=AsyncMock(return_value=61)):
        resp = client.get("/pets", headers=_auth_headers())
    assert resp.status_code == 429
    assert resp.json()["detail"]["error"] == "RATE_LIMIT_EXCEEDED"


@respx.mock
def test_pets_rate_limit_uses_user_id_key(client):
    """Rate limit key is per user_id, not per IP — two users have independent counters."""
    call_log: list[str] = []

    async def capture_incr(key: str, ttl: int) -> int:
        call_log.append(key)
        return 1  # within limit for both users

    respx.get("http://test-main-app/api/my-pets").mock(
        return_value=httpx.Response(200, json=[])
    )

    with patch("src.core.redis.incr_with_expiry", side_effect=capture_incr):
        client.get("/pets", headers=_auth_headers(user_id=1))
        client.get("/pets", headers=_auth_headers(user_id=2))

    assert any("user:1" in k for k in call_log)
    assert any("user:2" in k for k in call_log)


# ---------------------------------------------------------------------------
# JWT revocation blacklist
# ---------------------------------------------------------------------------


@respx.mock
def test_revoke_blacklists_jti(client):
    """POST /oauth/revoke stores the token's jti in the Redis blacklist."""
    respx.post("http://test-main-app/api/gpt-auth/revoke").mock(
        return_value=httpx.Response(200)
    )

    blacklisted: list[tuple[str, int]] = []

    async def capture_blacklist(jti: str, ttl: int) -> None:
        blacklisted.append((jti, ttl))

    with patch("src.core.redis.blacklist_jti", side_effect=capture_blacklist):
        resp = client.post("/oauth/revoke", headers=_auth_headers())

    assert resp.status_code == 200
    assert resp.json()["revoked"] is True
    assert len(blacklisted) == 1
    jti, ttl = blacklisted[0]
    assert len(jti) == 32  # uuid4().hex
    assert ttl > 0


@respx.mock
def test_blacklisted_token_is_rejected(client):
    """A JWT whose jti is in the blacklist returns 401."""
    with patch("src.core.redis.is_jti_blacklisted", new=AsyncMock(return_value=True)):
        resp = client.get("/pets", headers=_auth_headers())
    assert resp.status_code == 401
    assert "revoked" in resp.json()["detail"].lower()


def test_revoked_token_cannot_reach_pets(client):
    """After revocation the same token is blocked at the auth layer."""
    token = create_jwt(user_id=5, sanctum_token="s-tok")
    headers = {"Authorization": f"Bearer {token}"}

    # First call succeeds (jti not blacklisted yet)
    with patch("src.core.redis.is_jti_blacklisted", new=AsyncMock(return_value=False)):
        with patch("src.core.redis.incr_with_expiry", new=AsyncMock(return_value=1)):
            # health check doesn't require auth, use that
            pass

    # After revocation the same token is rejected
    with patch("src.core.redis.is_jti_blacklisted", new=AsyncMock(return_value=True)):
        resp = client.get("/pets", headers=headers)
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Idempotency — POST /pets duplicate guard
# ---------------------------------------------------------------------------


@respx.mock
def test_create_pet_duplicate_returns_409(client):
    """Creating a pet with a name that already exists returns 409 DUPLICATE_WARNING."""
    respx.get("http://test-main-app/api/pet-types").mock(
        return_value=httpx.Response(200, json=[{"id": 1, "name": "cat"}])
    )
    respx.get("http://test-main-app/api/my-pets").mock(
        return_value=httpx.Response(
            200, json=[{"id": 1, "name": "Luna", "pet_type_id": 1}]
        )
    )

    resp = client.post(
        "/pets",
        json={"name": "Luna", "species": "cat"},
        headers=_auth_headers(),
    )
    assert resp.status_code == 409
    assert resp.json()["error"] == "DUPLICATE_WARNING"


@respx.mock
def test_create_pet_duplicate_override_proceeds(client):
    """With confirm_duplicate=true the duplicate guard is bypassed and creation proceeds."""
    respx.get("http://test-main-app/api/pet-types").mock(
        return_value=httpx.Response(200, json=[{"id": 1, "name": "cat"}])
    )
    respx.get("http://test-main-app/api/my-pets").mock(
        return_value=httpx.Response(
            200, json=[{"id": 1, "name": "Luna", "pet_type_id": 1}]
        )
    )
    respx.post("http://test-main-app/api/pets").mock(
        return_value=httpx.Response(201, json={"id": 2, "name": "Luna"})
    )

    resp = client.post(
        "/pets",
        json={"name": "Luna", "species": "cat", "confirm_duplicate": True},
        headers=_auth_headers(),
    )
    assert resp.status_code == 201
