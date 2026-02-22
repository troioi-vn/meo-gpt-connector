"""
End-to-end OAuth flow tests: authorize → callback → token, plus edge cases.

Redis is faked via an in-memory dict so the full flow can be tested without
a real Redis server. httpx calls to the main app are intercepted by respx.
"""
import json
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
import respx

from src.core.jwt import validate_jwt


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_AUTHORIZE_PARAMS = {
    "client_id": "meo-gpt",
    "response_type": "code",
    "redirect_uri": "https://chatgpt.com/aip/oauth/callback",
    "state": "abc123",
}


def _make_stateful_redis():
    """Return a dict and patched async functions that share it."""
    store: dict[str, str] = {}

    async def _set(key, value, ttl):
        store[key] = value

    async def _get(key):
        return store.get(key)

    async def _delete(key):
        store.pop(key, None)

    async def _get_and_delete(key):
        return store.pop(key, None)

    patches = {
        "set_with_ttl": _set,
        "get": _get,
        "delete": _delete,
        "get_and_delete": _get_and_delete,
    }
    return store, patches


# ---------------------------------------------------------------------------
# /oauth/authorize
# ---------------------------------------------------------------------------

def test_authorize_success(client):
    store, fns = _make_stateful_redis()
    with (
        patch("src.core.redis.set_with_ttl", side_effect=fns["set_with_ttl"]),
    ):
        resp = client.get("/oauth/authorize", params=_VALID_AUTHORIZE_PARAMS, follow_redirects=False)

    assert resp.status_code == 302
    location = resp.headers["location"]
    assert "http://test-main-app/gpt-connect" in location
    assert "session_id=" in location
    assert "session_sig=" in location


def test_authorize_stores_session_in_redis(client):
    store, fns = _make_stateful_redis()
    with patch("src.core.redis.set_with_ttl", side_effect=fns["set_with_ttl"]):
        client.get("/oauth/authorize", params=_VALID_AUTHORIZE_PARAMS, follow_redirects=False)

    # Exactly one session key stored
    assert len(store) == 1
    key = next(iter(store))
    assert key.startswith("oauth:session:")
    session = json.loads(store[key])
    assert session["state"] == "abc123"
    assert session["redirect_uri"] == _VALID_AUTHORIZE_PARAMS["redirect_uri"]


def test_authorize_hmac_sig_is_deterministic(client):
    """Same session_id must always produce the same HMAC with the same secret."""
    import hashlib
    import hmac as hmac_lib

    store, fns = _make_stateful_redis()
    with patch("src.core.redis.set_with_ttl", side_effect=fns["set_with_ttl"]):
        resp = client.get("/oauth/authorize", params=_VALID_AUTHORIZE_PARAMS, follow_redirects=False)

    location = resp.headers["location"]
    parsed = urlparse(location)
    qs = parse_qs(parsed.query)
    session_id = qs["session_id"][0]
    returned_sig = qs["session_sig"][0]

    expected_sig = hmac_lib.new(
        b"test-hmac-secret", session_id.encode(), hashlib.sha256
    ).hexdigest()
    assert returned_sig == expected_sig


def test_authorize_invalid_client_id(client):
    params = {**_VALID_AUTHORIZE_PARAMS, "client_id": "wrong"}
    resp = client.get("/oauth/authorize", params=params)
    assert resp.status_code == 400
    assert "client_id" in resp.json()["detail"]


def test_authorize_invalid_response_type(client):
    params = {**_VALID_AUTHORIZE_PARAMS, "response_type": "token"}
    resp = client.get("/oauth/authorize", params=params)
    assert resp.status_code == 400


def test_authorize_missing_required_param(client):
    # FastAPI returns 422 for missing Query(...) params
    params = {k: v for k, v in _VALID_AUTHORIZE_PARAMS.items() if k != "state"}
    resp = client.get("/oauth/authorize", params=params)
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# /oauth/callback
# ---------------------------------------------------------------------------

@respx.mock
def test_callback_success(client):
    session_data = json.dumps({
        "state": "abc123",
        "redirect_uri": "https://chatgpt.com/aip/oauth/callback",
    })
    code_from_main_app = "main-app-code-xyz"

    respx.post("http://test-main-app/api/gpt-auth/exchange").mock(
        return_value=httpx.Response(200, json={"sanctum_token": "tok-abc", "user_id": 42})
    )

    store, fns = _make_stateful_redis()
    store["oauth:session:sess-123"] = session_data

    with (
        patch("src.core.redis.get", side_effect=fns["get"]),
        patch("src.core.redis.delete", side_effect=fns["delete"]),
        patch("src.core.redis.set_with_ttl", side_effect=fns["set_with_ttl"]),
    ):
        resp = client.get(
            "/oauth/callback",
            params={"session_id": "sess-123", "code": code_from_main_app},
            follow_redirects=False,
        )

    assert resp.status_code == 302
    location = resp.headers["location"]
    assert location.startswith("https://chatgpt.com/aip/oauth/callback")
    assert "code=" in location
    assert "state=abc123" in location


@respx.mock
def test_callback_session_deleted_after_exchange(client):
    session_data = json.dumps({
        "state": "xyz",
        "redirect_uri": "https://chatgpt.com/aip/oauth/callback",
    })
    respx.post("http://test-main-app/api/gpt-auth/exchange").mock(
        return_value=httpx.Response(200, json={"sanctum_token": "tok-abc", "user_id": 1})
    )
    store, fns = _make_stateful_redis()
    store["oauth:session:sess-del"] = session_data

    with (
        patch("src.core.redis.get", side_effect=fns["get"]),
        patch("src.core.redis.delete", side_effect=fns["delete"]),
        patch("src.core.redis.set_with_ttl", side_effect=fns["set_with_ttl"]),
    ):
        client.get(
            "/oauth/callback",
            params={"session_id": "sess-del", "code": "some-code"},
            follow_redirects=False,
        )

    assert "oauth:session:sess-del" not in store


def test_callback_expired_session_returns_html(client):
    with patch("src.core.redis.get", new_callable=AsyncMock, return_value=None):
        resp = client.get(
            "/oauth/callback",
            params={"session_id": "gone", "code": "whatever"},
        )

    assert resp.status_code == 400
    assert "text/html" in resp.headers["content-type"]
    assert "expired" in resp.text.lower()


@respx.mock
def test_callback_exchange_failure_returns_502(client):
    session_data = json.dumps({
        "state": "s",
        "redirect_uri": "https://chatgpt.com/aip/oauth/callback",
    })
    respx.post("http://test-main-app/api/gpt-auth/exchange").mock(
        return_value=httpx.Response(500)
    )
    store, fns = _make_stateful_redis()
    store["oauth:session:sess-err"] = session_data

    with (
        patch("src.core.redis.get", side_effect=fns["get"]),
        patch("src.core.redis.delete", side_effect=fns["delete"]),
        patch("src.core.redis.set_with_ttl", side_effect=fns["set_with_ttl"]),
    ):
        resp = client.get(
            "/oauth/callback",
            params={"session_id": "sess-err", "code": "bad"},
        )

    assert resp.status_code == 502


# ---------------------------------------------------------------------------
# /oauth/token
# ---------------------------------------------------------------------------

def test_token_success(client):
    code_data = json.dumps({"sanctum_token": "sanctum-tok", "user_id": 7})

    with patch("src.core.redis.get_and_delete", new_callable=AsyncMock, return_value=code_data):
        resp = client.post(
            "/oauth/token",
            data={
                "client_id": "meo-gpt",
                "client_secret": "test-client-secret",
                "grant_type": "authorization_code",
                "code": "some-code",
            },
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 31536000
    # Validate the JWT is decodable and contains the right user
    user_id, sanctum_token = validate_jwt(body["access_token"])
    assert user_id == 7
    assert sanctum_token == "sanctum-tok"


def test_token_invalid_client_secret(client):
    resp = client.post(
        "/oauth/token",
        data={
            "client_id": "meo-gpt",
            "client_secret": "wrong-secret",
            "grant_type": "authorization_code",
            "code": "any",
        },
    )
    assert resp.status_code == 401


def test_token_invalid_client_id(client):
    resp = client.post(
        "/oauth/token",
        data={
            "client_id": "bad-client",
            "client_secret": "test-client-secret",
            "grant_type": "authorization_code",
            "code": "any",
        },
    )
    assert resp.status_code == 401


def test_token_invalid_grant_type(client):
    resp = client.post(
        "/oauth/token",
        data={
            "client_id": "meo-gpt",
            "client_secret": "test-client-secret",
            "grant_type": "client_credentials",
            "code": "any",
        },
    )
    assert resp.status_code == 400


def test_token_expired_code(client):
    with patch("src.core.redis.get_and_delete", new_callable=AsyncMock, return_value=None):
        resp = client.post(
            "/oauth/token",
            data={
                "client_id": "meo-gpt",
                "client_secret": "test-client-secret",
                "grant_type": "authorization_code",
                "code": "expired-code",
            },
        )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# /oauth/revoke
# ---------------------------------------------------------------------------

def _make_valid_jwt() -> str:
    from src.core.jwt import create_jwt
    return create_jwt(user_id=1, sanctum_token="sanctum-tok-rev")


@respx.mock
def test_revoke_success(client):
    respx.post("http://test-main-app/api/gpt-auth/revoke").mock(
        return_value=httpx.Response(200)
    )
    resp = client.post(
        "/oauth/revoke",
        headers={"Authorization": f"Bearer {_make_valid_jwt()}"},
    )
    assert resp.status_code == 200
    assert resp.json()["revoked"] is True


@respx.mock
def test_revoke_best_effort_on_main_app_error(client):
    """If the main app fails, revoke still returns 200 (best-effort)."""
    respx.post("http://test-main-app/api/gpt-auth/revoke").mock(
        return_value=httpx.Response(500)
    )
    resp = client.post(
        "/oauth/revoke",
        headers={"Authorization": f"Bearer {_make_valid_jwt()}"},
    )
    assert resp.status_code == 200


def test_revoke_missing_token(client):
    resp = client.post("/oauth/revoke")
    assert resp.status_code in (401, 403)  # FastAPI HTTPBearer raises 4xx on missing auth


def test_revoke_invalid_jwt(client):
    resp = client.post(
        "/oauth/revoke",
        headers={"Authorization": "Bearer not.a.real.jwt"},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Full end-to-end flow
# ---------------------------------------------------------------------------

@respx.mock
def test_full_oauth_flow(client):
    """Emulate the complete authorize → callback → token sequence."""
    respx.post("http://test-main-app/api/gpt-auth/exchange").mock(
        return_value=httpx.Response(200, json={"sanctum_token": "e2e-tok", "user_id": 99})
    )

    store, fns = _make_stateful_redis()

    with (
        patch("src.core.redis.set_with_ttl", side_effect=fns["set_with_ttl"]),
        patch("src.core.redis.get", side_effect=fns["get"]),
        patch("src.core.redis.delete", side_effect=fns["delete"]),
        patch("src.core.redis.get_and_delete", side_effect=fns["get_and_delete"]),
    ):
        # Step 1: authorize → get session_id
        auth_resp = client.get(
            "/oauth/authorize", params=_VALID_AUTHORIZE_PARAMS, follow_redirects=False
        )
        assert auth_resp.status_code == 302
        location = auth_resp.headers["location"]
        session_id = parse_qs(urlparse(location).query)["session_id"][0]

        # Session must be in our fake store
        assert f"oauth:session:{session_id}" in store

        # Step 2: callback → get chatgpt_auth_code
        cb_resp = client.get(
            "/oauth/callback",
            params={"session_id": session_id, "code": "main-app-one-time-code"},
            follow_redirects=False,
        )
        assert cb_resp.status_code == 302
        cb_location = cb_resp.headers["location"]
        chatgpt_code = parse_qs(urlparse(cb_location).query)["code"][0]

        # Session gone, code stored
        assert f"oauth:session:{session_id}" not in store
        assert f"oauth:code:{chatgpt_code}" in store

        # Step 3: token exchange → JWT
        tok_resp = client.post(
            "/oauth/token",
            data={
                "client_id": "meo-gpt",
                "client_secret": "test-client-secret",
                "grant_type": "authorization_code",
                "code": chatgpt_code,
            },
        )
        assert tok_resp.status_code == 200
        body = tok_resp.json()
        user_id, sanctum_token = validate_jwt(body["access_token"])
        assert user_id == 99
        assert sanctum_token == "e2e-tok"

        # Code must be consumed (one-time use)
        assert f"oauth:code:{chatgpt_code}" not in store
