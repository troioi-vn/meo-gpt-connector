# meo-gpt-connector

This project is a connector between ChatGPT and Meo Mai Moi, a pet care management platform.
It allows users to manage their pets through a ChatGPT Custom GPT using natural language.

If you need to access the code of Meo Mai Moi, it's in `../meo-mai-moi` which has its own
CLAUDE.md file.

---

## Architecture Overview

```
User → ChatGPT Custom GPT → Actions (OpenAPI, Bearer JWT)
     → meo-gpt-connector (FastAPI, Python)
     → Meo Mai Moi API (Laravel + Sanctum)
     → PostgreSQL / S3 storage
```

### Key Decisions

- **Stack**: Python + FastAPI. OpenAPI schema auto-generated from Pydantic models.
- **Auth model**: Sanctum bridge. The connector acts as an OAuth2 Authorization Code server.
  It exchanges for Sanctum tokens from the main app, wraps them in signed JWTs for ChatGPT.
  The main app keeps Sanctum — no Passport needed.
- **Boundary**: Thin adapter. Connector normalizes inputs (species names → pet_type_id,
  approximate ages → birthday precision fields) and translates errors. No domain logic.
- **File handling**: No binary passthrough in MVP. GPT uses vision to extract structured data
  from uploaded photos/PDFs. Connector receives JSON, not files.
- **New users**: GPT integration is an open entry point. Users can register during the OAuth
  flow without an invitation code.

### JWT Token Design

The connector issues signed JWTs to ChatGPT. Each JWT contains the user's Sanctum token
encrypted with AES-256-GCM (so the connector is nearly stateless). Redis is only used during
the OAuth flow itself (short-lived auth codes, session state).

---

## Project Structure (target)

```
src/
├── main.py              # FastAPI app, middleware, router registration
├── routers/
│   ├── oauth.py         # /oauth/authorize, /oauth/callback, /oauth/token, /oauth/revoke
│   ├── pets.py          # /pets, /pets/{id}
│   ├── vaccinations.py  # /pets/{id}/vaccinations
│   ├── medical.py       # /pets/{id}/medical-records
│   └── weights.py       # /pets/{id}/weights
├── core/
│   ├── config.py        # Pydantic Settings (env vars)
│   ├── jwt.py           # Issue and validate JWTs
│   ├── crypto.py        # AES-256-GCM encrypt/decrypt
│   ├── redis.py         # Async Redis client
│   └── logging.py       # structlog setup
├── services/
│   └── main_app.py      # httpx client for main app API calls
└── models/
    ├── pets.py          # Pydantic request/response schemas
    ├── health.py        # Vaccination, medical, weight schemas
    └── errors.py        # Standardized error shapes
```

---

## Key Design Rules

1. **The GPT is an interpreter; the main app is the authority.** Never duplicate business logic.
2. **Semantic tools, not REST mirrors.** Connector endpoints are designed for LLM workflows, not
   1:1 with main app routes. A tool like `POST /pets/find` wraps a GET call + filtering logic.
   `POST /pets` includes an internal duplicate check. Tools can call multiple main app endpoints.
3. **Tool-friendly contracts.** Every field and endpoint description in the OpenAPI spec is read
   by the GPT as an instruction. Write descriptions as directives, not documentation.
4. **Structured errors always.** GPT recovers from errors if they are machine-readable. Never
   return unstructured messages.
5. **No tokens in logs.** Log `user_id`, `request_id`, `endpoint`, `status`, `latency_ms` only.
6. **Connector input is human-friendly; main app input is schema-exact.** The translation
   happens in the connector (e.g., "cat" → pet_type_id lookup, "6 months old" → birthday fields).
7. **Safe defaults.** Unknown `record_type` values → default to `"other"`. Unknown fields → drop
   rather than forward. The connector is the last sanitization layer before the main app.

---

## Environment Variables

```
MAIN_APP_URL=               # e.g. https://gpt.meo-mai-moi.com
CONNECTOR_API_KEY=          # Sent to main app for server-to-server exchange calls
OAUTH_CLIENT_ID=meo-gpt
OAUTH_CLIENT_SECRET=        # Checked when ChatGPT calls /oauth/token
JWT_SECRET=                 # Signs connector JWTs (HS256)
ENCRYPTION_KEY=             # AES-256-GCM key for Sanctum token in JWT payload
HMAC_SHARED_SECRET=         # Shared with main app for consent page HMAC validation
REDIS_URL=redis://localhost:6379
LOG_LEVEL=info
ENVIRONMENT=production
```

---

## Reference Documents

- `docs/plan-v1.1.md` — Full architecture plan (auth flow, API surface, phases).
- `docs/initial-tasks.md` — Ordered implementation task list.
- `../meo-mai-moi/tmp/gpt-connector-plan.md` — Changes needed in the main app.
- `docs/research/GPT-configuration-guide.md` — How to configure the Custom GPT in OpenAI.
- `docs/release.md` — Release process (versioning, git tags, branching).
