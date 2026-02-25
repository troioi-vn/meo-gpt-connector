from contextlib import asynccontextmanager
import os
from typing import AsyncGenerator

from fastapi import FastAPI

from src.core.config import get_settings
from src.core.logging import RequestLoggingMiddleware, setup_logging
from src.routers import admin, health, medical_records, oauth, pets, public, vaccinations, weights
from src.services.main_app import MainAppError, refresh_pet_types_cache


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()
    setup_logging(settings.LOG_LEVEL)
    try:
        await refresh_pet_types_cache(settings)
    except MainAppError:
        pass
    yield


def _openapi_server_url() -> str:
    return os.getenv("CONNECTOR_PUBLIC_URL", "http://localhost:8000").rstrip("/")

app = FastAPI(
    title="Meo GPT Connector",
    description="ChatGPT Custom GPT connector for Meo Mai Moi pet care platform.",
    version="0.1.0",
    servers=[{"url": _openapi_server_url()}],
    lifespan=lifespan,
)

app.add_middleware(RequestLoggingMiddleware)

app.include_router(health.router)
app.include_router(public.router)
app.include_router(admin.router)
app.include_router(oauth.router)
app.include_router(pets.router)
app.include_router(vaccinations.router)
app.include_router(medical_records.router)
app.include_router(weights.router)
