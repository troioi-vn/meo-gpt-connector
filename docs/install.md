# Developer Setup Guide

Everything you need to get the connector running locally, run tests, and understand the dev loop.

---

## Prerequisites

| Tool | Minimum version | Notes |
|---|---|---|
| Python | 3.12 | Check with `python3 --version` |
| Docker + Compose | 24 / 2.20 | Only needed for Docker-based run |
| Redis | 7 | Only needed for local run without Docker |

No `uv` requirement — plain `venv` + `pip` works fine. `uv` is faster if you have it.

---

## 1. Clone and create a virtual environment

```bash
git clone <repo-url>
cd meo-gpt-connector

python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
```

---

## 2. Install dependencies

**Development (includes test tools):**

```bash
pip install -e ".[dev]"
```

**Or with uv (faster):**

```bash
uv sync
```

---

## 3. Configure environment variables

```bash
cp .env.example .env
```

Open `.env` and fill in the values. For local development you only strictly need:

| Variable | What to put for local dev |
|---|---|
| `MAIN_APP_URL` | URL of a running Meo Mai Moi instance (or use a mock — see §6) |
| `CONNECTOR_API_KEY` | Any string, must match the main app's config |
| `OAUTH_CLIENT_SECRET` | Any string |
| `JWT_SECRET` | Any string, 32+ chars recommended |
| `ENCRYPTION_KEY` | 64 hex chars (32 bytes). Generate one: `python3 -c "import secrets; print(secrets.token_hex(32))"` |
| `HMAC_SHARED_SECRET` | Any string, must match the main app's config |
| `REDIS_URL` | `redis://localhost:6379` (default) |

The connector will refuse to start if any required variable is missing.

---

## 4a. Run with Docker Compose (recommended)

This starts Redis automatically alongside the connector:

```bash
docker compose up --build
```

- Connector: http://localhost:8001
- Health check: http://localhost:8001/health
- Interactive API docs: http://localhost:8001/docs

To run in the background:

```bash
docker compose up -d --build
docker compose logs -f connector   # follow logs
```

To stop:

```bash
docker compose down
```

---

## 4b. Run locally without Docker

You need Redis running separately:

```bash
# macOS
brew services start redis

# Ubuntu/Debian
sudo systemctl start redis

# Or run a one-off container
docker run -d -p 6379:6379 redis:7-alpine
```

Then start the connector:

```bash
uvicorn src.main:app --reload --host 0.0.0.0 --port 8001
```

`--reload` restarts on file changes. Useful during active development.

---

## 5. Verify it's working

```bash
curl http://localhost:8001/health
```

Expected response:

```json
{
  "status": "ok",
  "version": "0.2.0",
  "main_app_reachable": true
}
```

`main_app_reachable: false` is normal if `MAIN_APP_URL` isn't a live server — the connector still starts fine.

---

## 6. Run tests

Tests don't need a live main app or Redis — both are mocked.

Make sure your venv is activated (`source .venv/bin/activate`), then:

```bash
pytest
```

With coverage report:

```bash
pytest --cov=src --cov-report=term-missing
```

Run a specific file or test:

```bash
pytest tests/test_health.py -v
pytest tests/test_health.py::test_health_main_app_reachable -v
```

---

## Project layout

```
src/
├── main.py              # FastAPI app, middleware registration, router inclusion
├── core/
│   ├── config.py        # Pydantic Settings — reads .env, validates on startup
│   ├── logging.py       # structlog setup + HTTP request logging middleware
│   ├── jwt.py           # Issue and validate connector JWTs          (task 02)
│   ├── crypto.py        # AES-256-GCM encrypt/decrypt                (task 02)
│   └── redis.py         # Async Redis client                         (task 02)
├── routers/
│   ├── health.py        # GET /health
│   ├── oauth.py         # /oauth/authorize, /callback, /token, /revoke (task 03)
│   ├── pets.py          # /pets, /pets/{id}                          (task 05)
│   ├── vaccinations.py  # /pets/{id}/vaccinations                    (task 06)
│   ├── medical.py       # /pets/{id}/medical-records                 (task 06)
│   └── weights.py       # /pets/{id}/weights                         (task 06)
├── services/
│   └── main_app.py      # httpx client for main app calls            (task 05)
└── models/
    ├── pets.py           # Pydantic request/response schemas          (task 05)
    ├── health.py         # Vaccination, medical, weight schemas       (task 06)
    └── errors.py         # Standardized error shapes                 (task 03)

tests/
├── conftest.py          # TEST_SETTINGS fixture, patches lifespan + DI
└── test_health.py       # Health endpoint tests
```

---

## Common issues

**`ValidationError: Field required` on startup**
You're missing one or more required env vars. The error message lists which ones. Check your `.env` file.

**`ENCRYPTION_KEY must decode to exactly 32 bytes`**
The key must be exactly 64 hex characters. Generate a fresh one:
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

**Tests fail with `ConnectionRefused` to Redis**
Tests mock both the main app and Redis — they should never connect to either. If you see this, a test is accidentally hitting a real dependency. Check that the `client` fixture from `conftest.py` is being used.

**`main_app_reachable: false` in health response**
The connector couldn't reach `MAIN_APP_URL/api/version`. This is non-fatal — the connector runs normally. Point `MAIN_APP_URL` at a live Meo Mai Moi instance if you need the full OAuth flow.

**`MAIN_APP_URL=http://localhost:8000` doesn't work inside Docker**
Inside a Docker container, `localhost` is the container itself — not your host machine. Use `http://host.docker.internal:8000` instead (works on Docker Desktop / Linux with `extra_hosts`), or point at the real deployed URL.

---

## Useful commands

```bash
# Regenerate .env.example after adding a new variable to config.py
# (manual — just edit .env.example to match)

# Check what version the running connector reports
curl -s http://localhost:8001/health | python3 -m json.tool

# Follow connector logs (Docker)
docker compose logs -f connector

# Open a Redis CLI session (Docker)
docker compose exec redis redis-cli

# Rebuild only the connector image (without restarting Redis)
docker compose up -d --build connector
```

---

## GPT tool simulation script

For quick manual verification of connector tool behavior (the same sequence GPT Actions calls), use:

```bash
python scripts/simulate_gpt_tool_flow.py \
  --sanctum-token "<user_sanctum_token>" \
  --user-id <user_id>
```

The script will:
- try `POST /pets` through the connector,
- fallback to seeding one pet directly in the main app if create fails due upstream validation,
- run find/update/weight/vaccination/medical-record calls,
- print a JSON summary with all step statuses.

### Get a Sanctum token for local testing

From `../meo-mai-moi`:

```bash
docker compose exec -T backend php artisan tinker --execute='\
$u=\App\Models\User::where("email","admin@catarchy.space")->first(); \
echo $u->id."|".$u->createToken("gpt-sim", ["*"])->plainTextToken;'
```

Use the output as:
- `--user-id`: value before the first `|`
- `--sanctum-token`: everything after `<user_id>|`

## Full OAuth simulation script

To exercise the full bridge flow (`authorize -> confirm -> callback -> token`):

```bash
python scripts/simulate_oauth_flow.py \
  --sanctum-token "<user_sanctum_token>" \
  --verify-tools
```

This script:
- calls connector `GET /oauth/authorize`,
- calls main app `POST /api/gpt-auth/confirm` with your Sanctum token,
- follows connector callback,
- exchanges the one-time code at connector `POST /oauth/token`,
- optionally verifies the issued access token with connector `GET /pets`.

It prints a compact JSON trace of each step with status codes.

If `confirm` returns `Invalid session signature`, make sure connector `HMAC_SHARED_SECRET`
and main app `GPT_CONNECTOR_HMAC_SECRET` are exactly the same value.
