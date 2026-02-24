import base64
import secrets
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from src.core.admin_events import get_active_session_count, get_recent, get_total_event_count
from src.core.config import Settings, get_settings

_TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

router = APIRouter(prefix="/admin", tags=["admin"])


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
    except Exception:
        raise HTTPException(
            status_code=401,
            headers={"WWW-Authenticate": 'Basic realm="Meo GPT Admin"'},
        )

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
    events = await get_recent(n=50)
    return templates.TemplateResponse(request, "admin/partials/requests.html", {"events": events})


@router.get("/partials/errors", response_class=HTMLResponse, dependencies=[Depends(_require_admin)])
async def admin_errors(request: Request) -> HTMLResponse:
    events = await get_recent(n=50, errors_only=True)
    return templates.TemplateResponse(request, "admin/partials/errors.html", {"events": events})


@router.get("/partials/stats", response_class=HTMLResponse, dependencies=[Depends(_require_admin)])
async def admin_stats(request: Request) -> HTMLResponse:
    total_events, active_sessions, recent_errors = 0, 0, []
    try:
        total_events = await get_total_event_count()
        active_sessions = await get_active_session_count()
        recent_errors = await get_recent(n=50, errors_only=True)
    except Exception:
        pass
    return templates.TemplateResponse(
        request,
        "admin/partials/stats.html",
        {
            "total_events": total_events,
            "active_sessions": active_sessions,
            "error_count": len(recent_errors),
        },
    )
