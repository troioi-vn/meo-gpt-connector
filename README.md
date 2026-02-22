# meo-gpt-connector

A FastAPI service that connects a **ChatGPT Custom GPT** to **Meo Mai Moi** — a pet care platform
built in Vietnam for rescued cats and the people who care for them.

Users talk to the GPT in natural language. The connector translates that into API calls against the
main app, handles OAuth2 authentication, and shapes the responses so the GPT can reason about them.

> This project serves the same mission as Meo Mai Moi: helping people care for the animals who
> can't advocate for themselves. See the [project philosophy](../meo-mai-moi/docs/philosophy.md).

---

## What it does

**For users:**
- Connect their Meo Mai Moi account to ChatGPT with a one-click OAuth flow.
- New users can register during the flow — no invitation code required.
- Create pets, add vaccination records, log medical events, track weights — all by chatting.
- Ask questions: "Who has the closest birthday?" "What vaccinations are due next month?"
- Bulk entry from a photo: "Here's a photo of today's weight session" → ChatGPT reads it, connector stores it.

**For developers:**
- A semantic tool layer, not a REST proxy. Tools are designed for LLM workflows, not mirroring endpoints.
- Nearly stateless: JWTs issued to ChatGPT contain the Sanctum token encrypted inside (AES-256-GCM).
- Redis is only used during the OAuth handshake (short-lived codes). No user session database.

---

## Architecture

```
User
 └─ ChatGPT Custom GPT
      └─ Actions (OpenAPI / Bearer JWT)
           └─ meo-gpt-connector  ← this repo
                ├─ OAuth2 bridge (connector acts as OAuth2 server, delegates to Sanctum)
                ├─ Semantic tools (find_pet, create_pet with duplicate check, etc.)
                ├─ Input normalization ("cat" → pet_type_id, "6 months old" → birthday fields)
                └─ Main App API (Laravel + Sanctum, ../meo-mai-moi)
                      └─ PostgreSQL + S3
```

**Auth in one sentence:** ChatGPT redirects the user to the main app's consent page, the main app
returns a Sanctum token, the connector wraps it in a signed JWT and hands it to ChatGPT. Every
subsequent action call includes that JWT; the connector decrypts the Sanctum token and forwards it.

---

## Stack

| Concern | Choice |
|---|---|
| Framework | Python + FastAPI |
| Validation | Pydantic v2 |
| HTTP client | httpx (async) |
| Auth tokens | python-jose (JWT) + cryptography (AES-GCM) |
| Temp state | Redis (auth codes only) |
| Logging | structlog (JSON in prod) |
| Container | Docker (single container + Redis sidecar) |

---

## Project status

**In progress — Phase 1 (auth).**

Infrastructure and auth utilities are done (FastAPI, Docker, config, logging, health endpoint,
JWT, AES-256-GCM, Redis). Currently building the OAuth2 endpoints.
Architecture decisions are finalized in `docs/plan-v1.1.md`. Task tracker: `docs/plan/index.md`.

---

## Development setup

Full guide: **[docs/install.md](docs/install.md)**

```bash
git clone <repo-url> && cd meo-gpt-connector
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

cp .env.example .env
# Fill in .env (ENCRYPTION_KEY, JWT_SECRET, etc.)

docker compose up --build
# Connector: http://localhost:8001
# Health:    http://localhost:8001/health
# OpenAPI:   http://localhost:8001/docs

pytest   # all tests, no live services needed
```

---

## Key documents

| Document | Purpose |
|---|---|
| [`docs/install.md`](docs/install.md) | Dev setup, running locally, Docker, tests, common issues |
| [`docs/plan/index.md`](docs/plan/index.md) | Task tracker — what's done, what's next |
| [`docs/plan-v1.1.md`](docs/plan-v1.1.md) | Full architecture: auth flow, API surface, tool design, phases |
| [`docs/release.md`](docs/release.md) | Release process: versioning, git tags, branching |
| [`../meo-mai-moi/tmp/gpt-connector-plan.md`](../meo-mai-moi/tmp/gpt-connector-plan.md) | Changes needed in the main app |

---

## Related

- **[meo-mai-moi](../meo-mai-moi)** — the main app this connector talks to (Laravel + React)
- **[Catarchy](https://catarchy.space)** — where it all started
- **[Patreon](https://www.patreon.com/catarchy)** — how the project sustains itself

---

*Built in Vietnam. For the cats.*
