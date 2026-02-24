import logging
import time
import uuid
from typing import Any, Awaitable, Callable, cast

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


def setup_logging(log_level: str = "info") -> None:
    level = getattr(logging, log_level.upper(), logging.INFO)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(level=level)
    # httpx has its own stdlib logger that duplicates our structured logs
    logging.getLogger("httpx").setLevel(logging.WARNING)


def get_logger(name: str | None = None) -> structlog.BoundLogger:
    return cast(structlog.BoundLogger, structlog.get_logger(name))


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = str(uuid.uuid4())
        start = time.perf_counter()

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        response = await call_next(request)

        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        log = get_logger("http")
        log.info(
            "request",
            endpoint=str(request.url.path),
            method=request.method,
            status=response.status_code,
            latency_ms=latency_ms,
        )

        response.headers["X-Request-ID"] = request_id

        # Append to admin event log (best-effort; silently ignored if Redis is down)
        user_id: int | None = getattr(request.state, "user_id", None)
        event = {
            "request_id": request_id,
            "ts": time.time(),
            "method": request.method,
            "path": str(request.url.path),
            "user_id": user_id,
            "status": response.status_code,
            "latency_ms": latency_ms,
            "error_code": None,
        }
        try:
            from src.core.admin_events import append_event
            await append_event(event)
        except Exception:
            pass

        return response
