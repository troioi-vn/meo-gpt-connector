# Initial Implementation Tasks

Based on plan-v1.1.md. Work in these phases in order — each phase is a dependency for the next.

---

## Phase 0 — Infrastructure

Tasks for the `meo-gpt-connector` repo.

- [ ] **Init FastAPI project**
  - `src/` structure: `main.py`, `routers/`, `models/`, `services/`, `core/`
  - `pyproject.toml` (use `uv` or `poetry` for dependency management)
  - Dependencies: `fastapi`, `uvicorn`, `pydantic`, `httpx`, `python-jose[cryptography]`,
    `cryptography`, `redis`, `structlog`, `python-multipart`
    (`python-multipart` is required for FastAPI to parse `application/x-www-form-urlencoded`
    bodies — ChatGPT sends `POST /oauth/token` in this format)

- [ ] **Docker setup**
  - `Dockerfile` (multi-stage: build → slim runtime)
  - `docker-compose.yml` (connector + Redis)
  - `.env.example` with all required env vars (see plan-v1.1.md §10)

- [ ] **Configuration management**
  - `core/config.py` — Pydantic Settings model reading from env
  - All secrets required at startup (fail fast if missing)

- [ ] **Structured logging**
  - `structlog` setup with JSON output in production, pretty in dev
  - Request middleware: auto-log `request_id`, `endpoint`, `status`, `latency_ms`
  - Redact `Authorization` header from logs

- [ ] **GET /health endpoint**
  - Returns `{status: "ok", version: "...", main_app_reachable: bool}`
  - Checks main app by calling `GET {MAIN_APP_URL}/api/version`

- [ ] **Test infrastructure**
  - `pyproject.toml` test extras: `pytest`, `pytest-asyncio`, `respx`, `pytest-cov`
  - `tests/conftest.py`: settings override fixture, JWT factory helper
  - `pytest.ini` / `[tool.pytest.ini_options]`: asyncio mode, test paths, coverage config
  - `scripts/test-integration.sh`: convenience script for integration test run

- [ ] **CI skeleton**
  - GitHub Actions: lint (ruff), type-check (mypy), pytest (unit only), Docker build check

---

## Phase 1 — Authentication (Critical Path)

Blocks everything else. Do not start Phase 2 until auth is working end-to-end.

### Connector side

- [ ] **Redis client setup**
  - `core/redis.py` — async Redis client (via `redis.asyncio`)
  - Helper functions: `set_with_ttl`, `get_and_delete` (atomic for single-use codes)

- [ ] **JWT utilities**
  - `core/jwt.py` — issue and validate JWTs
  - Payload: `{sub: user_id, tok: encrypted_sanctum_token, iat, exp}`
  - Sign with `HS256` + `JWT_SECRET`

- [ ] **Sanctum token encryption**
  - `core/crypto.py` — AES-256-GCM encrypt/decrypt using `ENCRYPTION_KEY`
  - Used to store Sanctum token inside JWT payload

- [ ] **GET /oauth/authorize**
  - Validate `client_id`, `response_type`, `redirect_uri`
  - Generate `session_id`, compute HMAC sig
  - Store session in Redis (TTL 10 min)
  - Redirect to `{MAIN_APP_URL}/gpt-connect?session_id=...&session_sig=...`

- [ ] **GET /oauth/callback**
  - Validate `session_id` exists in Redis
  - Call `POST {MAIN_APP_URL}/api/gpt-auth/exchange` with Bearer `CONNECTOR_API_KEY`
  - On success: generate short-lived `chatgpt_auth_code`, store in Redis (TTL 5 min)
  - Redirect to `{redirect_uri}?code={chatgpt_auth_code}&state={state}`

- [ ] **POST /oauth/token**
  - Validate `client_id` + `client_secret`
  - Look up `chatgpt_auth_code` in Redis (get + delete atomically)
  - Decrypt Sanctum token, issue JWT
  - Return `{access_token, token_type: "bearer", expires_in: 31536000}`

- [ ] **POST /oauth/revoke** (basic)
  - Validate JWT, extract Sanctum token
  - Call `POST {MAIN_APP_URL}/api/gpt-auth/revoke` with Bearer `CONNECTOR_API_KEY`
    and body `{token: sanctum_token}` — main app deletes the token from the DB

- [ ] **Auth middleware for action endpoints**
  - FastAPI dependency: validate JWT, decrypt Sanctum token, attach to request state
  - Pass Sanctum token downstream in `Authorization: Bearer` header to main app

### Main app side (meo-mai-moi)

- [ ] **Config**: add `GPT_CONNECTOR_URL`, `GPT_CONNECTOR_API_KEY`, `GPT_CONNECTOR_HMAC_SECRET`
  to `.env.example` and `config/services.php`

- [ ] **Migration**: add `registered_via_gpt` boolean to `users` table

- [ ] **POST /api/gpt-auth/confirm** controller
  - HMAC validation, session replay protection
  - Create Sanctum token with GPT abilities
  - Store `auth_code → {user_id, sanctum_token}` in Redis (TTL 5 min)
  - Return `{redirect_url}`

- [ ] **POST /api/gpt-auth/exchange** controller
  - CONNECTOR_API_KEY guard
  - Look up + delete auth_code from Redis
  - Return `{sanctum_token, user_id}`

- [ ] **POST /api/gpt-auth/register** controller
  - HMAC validation
  - Registration without invite code
  - Set `registered_via_gpt = true`
  - Auto-login, return auth response

- [ ] **Frontend: `/gpt-connect` page**
  - React route `/gpt-connect`
  - HMAC validation via backend call on load
  - Three states: logged-in consent / login form / register form
  - i18n strings for all 4 languages

### Unit tests — Phase 1

- [ ] `tests/unit/test_jwt.py` — issue, validate, expire, tamper (see testing-plan.md)
- [ ] `tests/unit/test_crypto.py` — encrypt/decrypt round-trip, tamper detection
- [ ] `tests/unit/test_error_translation.py` — main app HTTP status → connector error code

### End-to-end auth test

- [ ] **Manual test**: ChatGPT → authorize → main app login → consent → connector callback → token
  issued → action call succeeds
- [ ] **New user test**: ChatGPT → authorize → register (no invite) → consent → works
- [ ] **Existing user test**: ChatGPT → authorize → already logged in → consent → works
- [ ] **Integration test**: `tests/integration/test_auth_flow.py` — OAuth2 flow via httpx
  (authorize → confirm → callback → token → action call)

---

## Phase 2 — Core API Endpoints

### Pet endpoints (connector)

- [ ] **GET /pets** — list user's pets
  - Maps to `GET /api/my-pets`
  - Returns simplified list (id, name, species, sex, age, photo_url)

- [ ] **GET /pet-types** — list available pet types
  - Maps to `GET /api/pet-types`
  - Cache in memory (pet types rarely change; refresh on startup)
  - Build internal `species_name → pet_type_id` lookup used by create/find tools

- [ ] **POST /pets/find** — semantic pet search tool
  - Accepts `{name, species}` (both optional)
  - Internally calls `GET /api/my-pets`, applies name/species filtering
  - Returns ranked candidates (exact name match first)
  - 0 results = not found, 1 = confident match, N = ambiguous (GPT asks user to confirm)

- [ ] **POST /pets** — create pet
  - Accepts human-friendly schema (species string, age_months, birth_month_year, birth_date)
  - Translates to main app schema (`species` → `pet_type_id`, date fields → precision fields)
  - Internal duplicate check (calls find logic) before creating
  - On duplicate: return `DUPLICATE_WARNING` with existing pet data + require `confirm_duplicate: true` to proceed

- [ ] **GET /pets/{id}** — map to `GET /api/pets/{id}`
  - Enrich response with upcoming vaccination due dates

- [ ] **PATCH /pets/{id}** — map to `PUT /api/pets/{id}`

### Health record endpoints (connector)

- [ ] **GET /pets/{id}/vaccinations** — map to `GET /api/pets/{id}/vaccinations`
- [ ] **POST /pets/{id}/vaccinations** — map to `POST /api/pets/{id}/vaccinations`
- [ ] **PATCH /pets/{id}/vaccinations/{vid}** — map to `PUT /api/pets/{id}/vaccinations/{vid}`
- [ ] **GET /pets/{id}/medical-records** — map to `GET /api/pets/{id}/medical-records`
- [ ] **POST /pets/{id}/medical-records** — map to `POST /api/pets/{id}/medical-records`
- [ ] **PATCH /pets/{id}/medical-records/{rid}** — map to `PUT /api/pets/{id}/medical-records/{rid}`
- [ ] **GET /pets/{id}/weights** — map to `GET /api/pets/{id}/weights`
- [ ] **POST /pets/{id}/weights** — map to `POST /api/pets/{id}/weights`

### Unit tests — Phase 2

- [ ] `tests/unit/test_normalization.py` — all three date input types, species lookup, invalid inputs
- [ ] `tests/unit/test_duplicate_filter.py` — 0/1/N match cases, species narrowing, case-insensitive

### Integration tests — Phase 2

- [ ] `tests/integration/conftest.py` — main app reachability check, test user fixture, auth_jwt fixture
- [ ] `tests/integration/test_pets.py` — full pet CRUD + find + duplicate warning + confirm_duplicate
- [ ] `tests/integration/test_vaccinations.py`
- [ ] `tests/integration/test_medical_records.py` — includes unknown record_type → "other" assertion
- [ ] `tests/integration/test_weights.py`

### Main app side

- [ ] Verify all needed endpoints exist and return JSON (not HTML on error)
- [ ] Verify `auth:sanctum` with token abilities works on write endpoints
- [ ] Note: `GET /api/my-pets` — connector does client-side filtering; no `?name=` param needed
  in the main app. If the main app later adds it, the connector can optionally use it as a
  pre-filter, but connector-side filtering is the design baseline (see plan-v1.1.md §12).

---

## Phase 3 — GPT Integration

- [ ] **OpenAPI spec review**
  - Check auto-generated spec is GPT-compatible (proper descriptions, enums, required fields)
  - Add `operationId` to all endpoints (ChatGPT uses these as tool names)
  - Add rich `description` to each endpoint and field

- [ ] **Create Custom GPT** in OpenAI GPT Builder
  - Name: "Meo Mai Moi"
  - Avatar: use app logo
  - Connect to `https://gpt.troioi.vn/openapi.json` (FastAPI serves this automatically)
  - Auth: OAuth2, Authorization Code flow
    - Authorization URL: `https://gpt.troioi.vn/oauth/authorize`
    - Token URL: `https://gpt.troioi.vn/oauth/token`
    - Client ID + Secret from connector config

- [ ] **Write GPT system prompt**
  - Core role description
  - Rules: never guess IDs, always call GET first to find pets, ask for missing fields
  - Language: respond in same language as user (vi/en/ru/uk)
  - Tool usage rules

- [ ] **End-to-end conversation tests**
  - Create pet with approximate age
  - Upload vaccination cert photo → GPT extracts data → record created
  - Add deworming medical record
  - "Which pet has the closest birthday?"
  - Bulk weight entry from photo

### Admin interface — Phase 2

- [ ] **`core/admin_events.py`** — write/read admin events in Redis sorted set
  - `append_event(event: dict)` — ZADD + trim to last 1000
  - `get_recent(n: int, errors_only: bool)` — ZREVRANGE + optional filter

- [ ] **Admin middleware** — HTTP Basic Auth check on all `/admin/*` routes
  - `ADMIN_ENABLED=false` → return 404 (no 401, don't reveal existence)
  - `ADMIN_ENABLED=true` + wrong password → 401

- [ ] **`routers/admin.py`** — route handlers
  - `GET /admin/` — full dashboard page
  - `GET /admin/partials/requests` — last 50 events table (HTMX target)
  - `GET /admin/partials/errors` — last 20 error events table (HTMX target)
  - `GET /admin/partials/stats` — stats bar: active sessions, call count, error count

- [ ] **Jinja2 templates** — `templates/admin/`
  - `base.html` — layout (version badge, env badge, nav)
  - `index.html` — dashboard page with HTMX polling (`hx-trigger="every 5s"`)
  - `partials/requests.html`, `partials/errors.html`, `partials/stats.html`

- [ ] **Wire middleware into request lifecycle** — existing request middleware calls
  `append_event()` after each response is sent (use Starlette `middleware` or `BackgroundTask`)

---

## Phase 4 — Hardening

- [ ] **Rate limiting** — per-IP and per-token limits on all action endpoints
- [ ] **Idempotency guard on POST /pets** — query for duplicate before creating
- [ ] **Error taxonomy** — review all error codes, ensure all are GPT-recoverable
- [ ] **Token revocation blacklist** — Redis-based if main app doesn't support token delete
- [ ] **Alerting** — set up monitoring for 5xx rate, auth failures, latency (see plan-v1.1.md §10)
- [ ] **Load test** — simulate GPT burst calls, verify rate limits hold

---

## Phase 5 — Post-Launch Enhancements

- [ ] Binary file passthrough (download from OpenAI CDN, re-upload to main app)
  - Requires extending main app to accept PDFs in VaccinationRecord media collection
- [ ] Computed query endpoints (e.g., `GET /pets/vaccinations/upcoming?days=90`)
- [ ] Webhook support (notify GPT when main app data changes? — evaluate need)
- [ ] Zalo OA integration (reuse connector service layer with different entry point)
