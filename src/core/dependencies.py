from fastapi import HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.core.jwt import validate_jwt

_bearer = HTTPBearer()


async def get_current_token(
    credentials: HTTPAuthorizationCredentials = Security(_bearer),
) -> tuple[int, str]:
    """Validate Bearer JWT. Returns (user_id, sanctum_token).

    Raises 401 on expired/invalid JWT, 403 if Authorization header is absent.
    """
    try:
        return validate_jwt(credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc))
