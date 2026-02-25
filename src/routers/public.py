from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

_TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

router = APIRouter(tags=["public"])


@router.get("/privacy", response_class=HTMLResponse, include_in_schema=False)
async def privacy_policy(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "public/privacy.html")
