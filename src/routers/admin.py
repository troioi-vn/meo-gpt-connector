import base64
import secrets
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from src.core.admin_events import get_active_session_count, get_recent, get_total_event_count
from src.core.config import Settings, get_settings

_TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

router = APIRouter(prefix="/admin", tags=["admin"])

_TOOL_PATH_PREFIXES = ["/pets", "/pet-types"]
_AUTH_PATH_PREFIXES = ["/oauth/"]
_CONNECTOR_ERROR_PATH_PREFIXES = [*_TOOL_PATH_PREFIXES, *_AUTH_PATH_PREFIXES, "/health"]
_USER_ERROR_STATUSES = {400, 401, 403, 404, 409, 422, 429}
_UPSTREAM_ERROR_STATUSES = {502, 503, 504}


def _classify_error(event: dict[str, Any]) -> dict[str, Any]:
    status = int(event.get("status") or 0)

    if status in _UPSTREAM_ERROR_STATUSES:
        category = "upstream"
        label = "Upstream"
    elif status >= 500:
        category = "connector"
        label = "Connector"
    elif status in _USER_ERROR_STATUSES:
        category = "user"
        label = "User/Input"
    else:
        category = "other"
        label = "Other"

    enriched = dict(event)
    enriched["error_category"] = category
    enriched["error_category_label"] = label
    return enriched


async def _require_admin(request: Request, settings: Settings = Depends(get_settings)) -> None:
    """Dependency: return 404 if admin disabled, 401 if credentials are wrong."""
    if not settings.ADMIN_ENABLED:
        raise HTTPException(status_code=404)

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Basic "):
        raise HTTPException(
            status_code=401,
            headers={"WWW-Authenticate": 'Basic realm="Meo GPT Admin"'},
            detail="Authentication required",
        )
    try:
        decoded = base64.b64decode(auth_header[6:]).decode()
        username, password = decoded.split(":", 1)
    except Exception as exc:
        raise HTTPException(
            status_code=401,
            headers={"WWW-Authenticate": 'Basic realm="Meo GPT Admin"'},
        ) from exc

    password_ok = secrets.compare_digest(password.encode(), settings.ADMIN_PASSWORD.encode())
    if username != "admin" or not password_ok:
        raise HTTPException(
            status_code=401,
            headers={"WWW-Authenticate": 'Basic realm="Meo GPT Admin"'},
        )


@router.get("/", response_class=HTMLResponse, dependencies=[Depends(_require_admin)])
async def admin_index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "admin/index.html")


@router.get("/partials/requests", response_class=HTMLResponse, dependencies=[Depends(_require_admin)])
async def admin_requests(request: Request) -> HTMLResponse:
    events = await get_recent(n=50, include_paths=_TOOL_PATH_PREFIXES, skip_admin=True)
    return templates.TemplateResponse(request, "admin/partials/requests.html", {"events": events})


@router.get("/partials/errors", response_class=HTMLResponse, dependencies=[Depends(_require_admin)])
async def admin_errors(request: Request) -> HTMLResponse:
    raw_events = await get_recent(
        n=50,
        errors_only=True,
        skip_admin=True,
        include_paths=_CONNECTOR_ERROR_PATH_PREFIXES,
    )
    events = [_classify_error(event) for event in raw_events]
    return templates.TemplateResponse(
        request,
        "admin/partials/errors.html",
        {
            "events": events,
            "user_error_count": sum(1 for event in events if event["error_category"] == "user"),
            "upstream_error_count": sum(1 for event in events if event["error_category"] == "upstream"),
            "connector_error_count": sum(1 for event in events if event["error_category"] == "connector"),
        },
    )


@router.get("/partials/auth", response_class=HTMLResponse, dependencies=[Depends(_require_admin)])
async def admin_auth(request: Request) -> HTMLResponse:
    events = await get_recent(n=50, include_paths=_AUTH_PATH_PREFIXES, skip_admin=True)
    return templates.TemplateResponse(request, "admin/partials/auth.html", {"events": events})


@router.get("/partials/stats", response_class=HTMLResponse, dependencies=[Depends(_require_admin)])
async def admin_stats(request: Request) -> HTMLResponse:
    total_events, active_sessions = 0, 0
    signal_events: list[dict] = []
    tool_events: list[dict] = []
    auth_events: list[dict] = []
    recent_errors: list[dict] = []
    try:
        total_events = await get_total_event_count()
        active_sessions = await get_active_session_count()
        signal_events = await get_recent(n=500, skip_admin=True)
        tool_events = await get_recent(n=200, include_paths=_TOOL_PATH_PREFIXES, skip_admin=True)
        auth_events = await get_recent(n=200, include_paths=_AUTH_PATH_PREFIXES, skip_admin=True)
        recent_errors = await get_recent(
            n=50,
            errors_only=True,
            skip_admin=True,
            include_paths=_CONNECTOR_ERROR_PATH_PREFIXES,
        )
    except Exception:
        pass

    successful_logins = [
        event for event in auth_events
        if event.get("path") == "/oauth/token" and event.get("status", 0) < 400
    ]
    auth_errors = [event for event in auth_events if event.get("status", 0) >= 400]

    return templates.TemplateResponse(
        request,
        "admin/partials/stats.html",
        {
            "total_events": total_events,
            "signal_events": len(signal_events),
            "tool_events": len(tool_events),
            "active_sessions": active_sessions,
            "error_count": len(recent_errors),
            "successful_logins": len(successful_logins),
            "auth_error_count": len(auth_errors),
        },
    )
