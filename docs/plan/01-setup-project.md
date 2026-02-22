# 01 - Setup Project (Infrastructure)

**Goal:** Establish the FastAPI skeleton, Docker configuration, secrets management, structured logging, and basic CI.

## Definition of Done

- A running FastAPI server initialized by `uvicorn`.
- `GET /health` returns `{status: "ok", version: "...", main_app_reachable: bool}`.
- Docker multi-stage build works (`connector` + `redis` in `docker-compose.yml`).
- Configuration via Pydantic `Settings` (reads `.env`).
- Structured `structlog` setup.
- Basic test infrastructure in place with `pytest`.

## Implementation Steps

1. **Init PyProject:**
   - Use `uv` or `poetry` (creating `pyproject.toml`).
   - Add dependencies: `fastapi`, `uvicorn`, `pydantic`, `httpx`, `python-jose[cryptography]`, `cryptography`, `redis`, `structlog`, `python-multipart`.
   - Add test dependencies: `pytest`, `pytest-asyncio`, `respx`, `pytest-cov`.
2. **Directory Structure:**
   - Create `src/main.py`
   - Create folders: `src/routers/`, `src/models/`, `src/services/`, `src/core/`.
3. **Configuration (`src/core/config.py`):**
   - Create a Pydantic `BaseSettings` class.
   - Required fields: `MAIN_APP_URL`, `CONNECTOR_API_KEY`, `OAUTH_CLIENT_ID`, `OAUTH_CLIENT_SECRET`, `JWT_SECRET`, `ENCRYPTION_KEY`, `HMAC_SHARED_SECRET`, `REDIS_URL` (usually `redis://localhost:6379`).
   - Throw an error on startup if these are missing.
4. **Structured Logging (`src/core/logging.py`):**
   - Setup `structlog`.
   - Add a custom middleware in `main.py` to auto-log `request_id`, `endpoint`, `status`, `latency_ms` for every HTTP hit.
   - Redact `Authorization` headers in logs.

5. **Docker & Compose:**
   - Create a multi-stage `Dockerfile`.
   - Create `docker-compose.yml` including the connector image and a `redis:alpine` container.

6. **Health Endpoint (`src/routers/health.py` or similar):**
   - Route `GET /health`.
   - Call `GET {MAIN_APP_URL}/api/version` (catch network errors instead of crashing).
   - Return `{status: "ok", version: "<read from pyproject>", main_app_reachable: True/False}`.

7. **Basic Tests:**
   - `tests/conftest.py`: Override test settings.
   - Write a unit test asserting `GET /health` acts correctly depending on whether the main app is reachable (mock via `respx`).
