import uuid as _uuid
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from jose import JWTError, jwt

from src.core.config import get_settings
from src.core.crypto import decrypt, encrypt

_ALGORITHM = "HS256"
_LIFETIME_DAYS = 365


def create_jwt(user_id: int, sanctum_token: str) -> str:
    """Issue a signed JWT embedding an AES-encrypted Sanctum token.

    Payload claims:
      sub — user ID (string, per JWT spec)
      tok — AES-256-GCM encrypted Sanctum token
      exp — 1 year from now
      jti — unique token ID for revocation blacklisting
    """
    settings = get_settings()
    exp = int((datetime.now(UTC) + timedelta(days=_LIFETIME_DAYS)).timestamp())
    payload = {
        "sub": str(user_id),
        "tok": encrypt(sanctum_token),
        "exp": exp,
        "jti": _uuid.uuid4().hex,
    }
    return cast(str, jwt.encode(payload, settings.JWT_SECRET, algorithm=_ALGORITHM))


def validate_jwt(token: str) -> tuple[int, str]:
    """Decode and verify a JWT. Returns (user_id, sanctum_token).

    Raises ValueError on expiry, invalid signature, or any tampering.
    """
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[_ALGORITHM])
    except JWTError as exc:
        raise ValueError(f"Invalid token: {exc}") from exc
    return int(payload["sub"]), decrypt(payload["tok"])


def get_jwt_meta(token: str) -> tuple[str | None, int]:
    """Return (jti, exp) from a validated JWT. Returns (None, 0) on any error.

    Call only after validate_jwt() has already succeeded. Used to extract
    revocation and expiry metadata without re-raising.
    """
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[_ALGORITHM])
        return payload.get("jti"), int(payload.get("exp") or 0)
    except JWTError:
        return None, 0
