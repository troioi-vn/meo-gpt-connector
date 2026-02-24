from typing import Annotated

from fastapi import Depends, HTTPException, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.core import redis as redis_store
from src.core.config import Settings, get_settings
from src.core.jwt import get_jwt_meta, validate_jwt
from src.core.rate_limit import check_rate_limit

_bearer = HTTPBearer()


async def get_current_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Security(_bearer),
) -> tuple[int, str]:
    """Validate Bearer JWT. Returns (user_id, sanctum_token).

    Also sets request.state.user_id, request.state.jti, and request.state.token_exp
    for middleware event logging and revocation handling.
    Raises 401 on expired/invalid/revoked JWT, 403 if Authorization header is absent.
    """
    try:
        user_id, sanctum_token = validate_jwt(credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    jti, exp = get_jwt_meta(credentials.credentials)

    if jti and await redis_store.is_jti_blacklisted(jti):
        raise HTTPException(status_code=401, detail="Token has been revoked")

    request.state.user_id = user_id
    request.state.jti = jti
    request.state.token_exp = exp
    return user_id, sanctum_token


async def get_current_token_limited(
    request: Request,
    current: Annotated[tuple[int, str], Depends(get_current_token)],
    settings: Settings = Depends(get_settings),
) -> tuple[int, str]:
    """Like get_current_token but also enforces per-user rate limiting."""
    user_id, _ = current
    await check_rate_limit(f"user:{user_id}", settings.RATE_LIMIT_PER_MINUTE)
    return current
