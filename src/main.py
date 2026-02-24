from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.core.config import get_settings
from src.core.logging import RequestLoggingMiddleware, setup_logging
from src.routers import admin, health, oauth, pets, vaccinations, medical_records, weights
from src.services.main_app import MainAppError, refresh_pet_types_cache


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    setup_logging(settings.LOG_LEVEL)
    try:
        await refresh_pet_types_cache(settings)
    except MainAppError:
        pass
    yield


app = FastAPI(
    title="Meo GPT Connector",
    description="ChatGPT Custom GPT connector for Meo Mai Moi pet care platform.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(RequestLoggingMiddleware)

app.include_router(health.router)
app.include_router(admin.router)
app.include_router(oauth.router)
app.include_router(pets.router)
app.include_router(vaccinations.router)
app.include_router(medical_records.router)
app.include_router(weights.router)
