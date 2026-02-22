from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.core.config import get_settings
from src.core.logging import RequestLoggingMiddleware, setup_logging
from src.routers import health


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    setup_logging(settings.LOG_LEVEL)
    yield


app = FastAPI(
    title="Meo GPT Connector",
    description="ChatGPT Custom GPT connector for Meo Mai Moi pet care platform.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(RequestLoggingMiddleware)

app.include_router(health.router)
