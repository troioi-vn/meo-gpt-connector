import hashlib
import hmac
import json
import uuid
from datetime import UTC, datetime
from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from src.core import redis as redis_store
from src.core.config import Settings, get_settings
from src.core.dependencies import get_current_token
from src.core.jwt import create_jwt
from src.core.rate_limit import check_rate_limit
from src.services.main_app import MainAppError, exchange_code, revoke_token

router = APIRouter(prefix="/oauth", tags=["oauth"])

_SESSION_TTL = 600  # 10 minutes
_CODE_TTL = 300     # 5 minutes


@router.get("/authorize")
async def authorize(
    request: Request,
    client_id: str = Query(...),
    response_type: str = Query(...),
    redirect_uri: str = Query(...),
    state: str = Query(...),
    settings: Settings = Depends(get_settings),
):
    client_ip = request.client.host if request.client else "unknown"
    await check_rate_limit(f"ip:{client_ip}", settings.RATE_LIMIT_PER_MINUTE)

    if client_id != settings.OAUTH_CLIENT_ID:
        raise HTTPException(status_code=400, detail="Invalid client_id")
    if response_type != "code":
        raise HTTPException(status_code=400, detail="response_type must be 'code'")
    if not redirect_uri:
        raise HTTPException(status_code=400, detail="redirect_uri is required")

    session_id = str(uuid.uuid4())
    sig = hmac.new(
        settings.HMAC_SHARED_SECRET.encode(),
        session_id.encode(),
        hashlib.sha256,
    ).hexdigest()

    session_data = json.dumps({"state": state, "redirect_uri": redirect_uri})
    await redis_store.set_with_ttl(f"oauth:session:{session_id}", session_data, _SESSION_TTL)

    query = urlencode({"session_id": session_id, "session_sig": sig})
    return RedirectResponse(url=f"{settings.MAIN_APP_URL}/gpt-connect?{query}", status_code=302)


@router.get("/callback")
async def callback(
    session_id: str = Query(...),
    code: str = Query(...),
    settings: Settings = Depends(get_settings),
):
    raw = await redis_store.get(f"oauth:session:{session_id}")
    if raw is None:
        return HTMLResponse(
            content=(
                "<html><body>"
                "<h1>Session Expired</h1>"
                "<p>Your login session has expired or is invalid. "
                "Please return to ChatGPT and try again.</p>"
                "</body></html>"
            ),
            status_code=400,
        )

    session = json.loads(raw)
    state = session["state"]
    redirect_uri = session["redirect_uri"]

    try:
        data = await exchange_code(code, settings)
    except MainAppError as exc:
        if exc.status_code in (401, 404, 422):
            raise HTTPException(status_code=502, detail="Main app exchange failed") from exc
        raise HTTPException(status_code=502, detail="Main app exchange failed") from exc

    await redis_store.delete(f"oauth:session:{session_id}")

    chatgpt_auth_code = str(uuid.uuid4())
    code_data = json.dumps({"sanctum_token": data["sanctum_token"], "user_id": data["user_id"]})
    await redis_store.set_with_ttl(f"oauth:code:{chatgpt_auth_code}", code_data, _CODE_TTL)

    query = urlencode({"code": chatgpt_auth_code, "state": state})
    return RedirectResponse(url=f"{redirect_uri}?{query}", status_code=302)


@router.post("/token")
async def token(
    client_id: Annotated[str, Form()],
    client_secret: Annotated[str, Form()],
    grant_type: Annotated[str, Form()],
    code: Annotated[str, Form()],
    settings: Settings = Depends(get_settings),
):
    if client_id != settings.OAUTH_CLIENT_ID or client_secret != settings.OAUTH_CLIENT_SECRET:
        raise HTTPException(status_code=401, detail="Invalid client credentials")
    if grant_type != "authorization_code":
        raise HTTPException(status_code=400, detail="Unsupported grant_type")

    raw = await redis_store.get_and_delete(f"oauth:code:{code}")
    if raw is None:
        raise HTTPException(status_code=400, detail="Invalid or expired code")

    code_data = json.loads(raw)
    jwt_token = create_jwt(code_data["user_id"], code_data["sanctum_token"])

    return {"access_token": jwt_token, "token_type": "bearer", "expires_in": 31536000}


@router.post("/revoke", status_code=200)
async def revoke(
    request: Request,
    current: Annotated[tuple[int, str], Depends(get_current_token)],
    settings: Settings = Depends(get_settings),
):
    _, sanctum_token = current

    # Blacklist the JWT so it cannot be used again after revocation.
    jti = getattr(request.state, "jti", None)
    token_exp = getattr(request.state, "token_exp", 0)
    if jti:
        remaining_ttl = max(1, token_exp - int(datetime.now(UTC).timestamp()))
        await redis_store.blacklist_jti(jti, ttl=remaining_ttl)

    try:
        await revoke_token(sanctum_token, settings)
    except MainAppError:
        pass  # Best-effort: don't surface main app errors to the caller
    return {"revoked": True}
