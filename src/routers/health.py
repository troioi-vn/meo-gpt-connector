import sys
from importlib.metadata import version, PackageNotFoundError

import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from src.core.config import Settings, get_settings

router = APIRouter()


def _get_version() -> str:
    try:
        return version("meo-gpt-connector")
    except PackageNotFoundError:
        pass

    try:
        if sys.version_info >= (3, 11):
            import tomllib
        else:
            import tomllib  # type: ignore[no-redef]

        with open("pyproject.toml", "rb") as f:
            data = tomllib.load(f)
        return data["project"]["version"]
    except Exception:
        return "unknown"


class HealthResponse(BaseModel):
    status: str
    version: str
    main_app_reachable: bool


@router.get("/health", response_model=HealthResponse)
async def health_check(settings: Settings = Depends(get_settings)) -> HealthResponse:
    main_app_reachable = False
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{settings.MAIN_APP_URL}/api/version")
            main_app_reachable = resp.status_code < 500
    except Exception:
        main_app_reachable = False

    return HealthResponse(
        status="ok",
        version=_get_version(),
        main_app_reachable=main_app_reachable,
    )
