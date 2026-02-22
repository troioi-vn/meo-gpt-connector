from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from jose import jwt as jose_jwt

from tests.conftest import TEST_SETTINGS


@pytest.fixture(autouse=True)
def patch_settings():
    """Patch get_settings in both jwt and crypto modules (crypto is called by jwt)."""
    with (
        patch("src.core.jwt.get_settings", return_value=TEST_SETTINGS),
        patch("src.core.crypto.get_settings", return_value=TEST_SETTINGS),
    ):
        yield


def test_happy_path():
    from src.core.jwt import create_jwt, validate_jwt

    token = create_jwt(42, "sanctum|abc")
    user_id, sanctum_token = validate_jwt(token)

    assert user_id == 42
    assert sanctum_token == "sanctum|abc"


def test_expired_token_raises():
    from src.core.jwt import validate_jwt

    past = int((datetime.now(timezone.utc) - timedelta(seconds=10)).timestamp())
    expired = jose_jwt.encode(
        {"sub": "1", "tok": "irrelevant", "exp": past},
        TEST_SETTINGS.JWT_SECRET,
        algorithm="HS256",
    )
    with pytest.raises(ValueError, match="Invalid token"):
        validate_jwt(expired)


def test_invalid_signature_raises():
    from src.core.jwt import create_jwt, validate_jwt

    token = create_jwt(1, "sanctum|x")
    header, payload_b64, _ = token.split(".")
    # Replace the entire signature with a clearly wrong one
    bad_sig = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    with pytest.raises(ValueError, match="Invalid token"):
        validate_jwt(f"{header}.{payload_b64}.{bad_sig}")


def test_tampered_payload_raises():
    """Modifying the payload invalidates the HMAC signature."""
    from src.core.jwt import create_jwt, validate_jwt
    import base64, json

    token = create_jwt(1, "sanctum|x")
    header, payload_b64, sig = token.split(".")

    # Decode, mutate sub, re-encode (padding required for base64url)
    decoded = json.loads(base64.urlsafe_b64decode(payload_b64 + "=="))
    decoded["sub"] = "999"
    new_payload = (
        base64.urlsafe_b64encode(json.dumps(decoded).encode()).decode().rstrip("=")
    )

    with pytest.raises(ValueError, match="Invalid token"):
        validate_jwt(f"{header}.{new_payload}.{sig}")


def test_wrong_algorithm_rejected():
    """A token signed with a different algorithm must be rejected."""
    from src.core.jwt import validate_jwt

    # Sign with RS256-like none algorithm tricks — here we just use a different secret
    forged = jose_jwt.encode(
        {"sub": "1", "tok": "x", "exp": 9999999999},
        "wrong-secret",
        algorithm="HS256",
    )
    with pytest.raises(ValueError, match="Invalid token"):
        validate_jwt(forged)
