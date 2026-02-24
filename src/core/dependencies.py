from fastapi import HTTPException, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.core.jwt import validate_jwt

_bearer = HTTPBearer()


async def get_current_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Security(_bearer),
) -> tuple[int, str]:
    """Validate Bearer JWT. Returns (user_id, sanctum_token).

    Also sets request.state.user_id for middleware event logging.
    Raises 401 on expired/invalid JWT, 403 if Authorization header is absent.
    """
    try:
        user_id, sanctum_token = validate_jwt(credentials.credentials)
        request.state.user_id = user_id
        return user_id, sanctum_token
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc))
