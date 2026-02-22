# meo-gpt-connector — Architecture Plan v1.1

Date: 2026-02-22
Status: Accepted design baseline. Supersedes plan-v1.0.

---

## 1. Purpose & Product Vision

`meo-gpt-connector` is a standalone FastAPI service that lets users of the Meo Mai Moi pet care
platform manage their pets through a ChatGPT Custom GPT using natural language.

### What users can do

**Complex pet creation**
> "Create a new cat named Clauddy. Here is her vaccination certificate [photo]. We don't know her
> exact birthday, but she's about 6 months old. She was dewormed 2 months ago."

The GPT processes language, calls tools in sequence: check for duplicates → create pet → extract
vaccination data from photo → store vaccination record → store medical record (deworming).

**Smart queries**
> "Which of my pets has the closest birthday?"
> "What vaccinations does my dog need in the next 3 months?"
> "I'm going on holiday for a week — summarize my pets' care routines."

The GPT calls read endpoints, then reasons over the returned data. No special summary endpoint
needed: the API provides the facts, the LLM provides the synthesis.

**Bulk data entry from a photo**
> "I weighed all 3 of my cats today. Here's the photo of my notes."

The GPT uses its vision to extract weight data from the photo, calls the pet list to match names to
IDs, then calls the weight endpoint for each pet.

### What the connector is NOT

- Not a second system of record.
- Not an AI pipeline (no OCR, no LLM calls).
- Not a UI — it is purely an HTTP adapter between ChatGPT and the main app API.

---

## 2. Key Decisions (Finalized)

| Decision | Choice | Rationale |
|---|---|---|
| Stack | Python + FastAPI | OpenAPI-first, auto-generates schema ChatGPT reads |
| Auth | Sanctum bridge (connector as OAuth2 server) | Avoids Passport, minimal main app impact |
| New user flow | GPT = open entry point, no invite required | ChatGPT integration is its own onboarding channel |
| File handling | GPT extracts structured data; no binary passthrough | Simpler MVP; GPT has vision built-in |
| MVP scope | Full vision MVP (including bulk weight from photo) | All cases rely on GPT vision, connector just receives JSON |
| Boundary | Thin adapter | Connector normalizes input, main app owns domain logic |

---

## 3. System Architecture

```
User
 └─ ChatGPT Custom GPT
      └─ Actions (OpenAPI, Bearer JWT)
           └─ meo-gpt-connector (FastAPI)
                ├─ OAuth2 layer (issues/validates JWTs)
                ├─ Request normalization (species names → pet_type_id, age → birthday fields)
                ├─ Error translation (backend errors → GPT-recoverable messages)
                └─ Main App API (Laravel + Sanctum)
                      └─ PostgreSQL / S3-compatible storage
```

### Layer responsibilities

**ChatGPT GPT**
- Understands natural language and user intent.
- Asks clarifying questions when required fields are missing.
- Calls tools only when all required data is available.
- Uses vision to extract structured data from photos/PDFs.
- Never invents IDs or stored data.

**Connector (this project)**
- Implements OAuth2 Authorization Code flow on top of Sanctum.
- Issues and validates JWTs for ChatGPT.
- Translates human-friendly inputs to backend schemas (e.g., species → pet_type_id).
- Translates approximate dates to precision-aware birthday fields.
- Shapes errors into structured, GPT-recoverable responses.
- Rate-limits and logs all requests.

**Main App (meo-mai-moi)**
- Owns all domain data and business rules.
- Source of truth for pets, health records, users.
- Performs computed outputs (upcoming due dates, ages).

---

## 4. Authentication: Sanctum Bridge

The main app uses Laravel Sanctum (session/token auth). ChatGPT Actions require OAuth2
Authorization Code flow. The connector bridges these by acting as an OAuth2 server that internally
exchanges for Sanctum tokens.

### 4.1 OAuth2 Flow (Step by Step)

```
1. User attempts first GPT action
2. ChatGPT opens browser: GET https://gpt.troioi.vn/oauth/authorize
        ?client_id=meo-gpt
        &redirect_uri=https://chat.openai.com/.../callback
        &response_type=code
        &state={opaque_state}

3. Connector /oauth/authorize:
   - Validates client_id
   - Generates session_id (UUID)
   - Signs session: sig = HMAC-SHA256(session_id, SHARED_SECRET)
   - Stores in Redis (TTL 10 min): session_id → {state, redirect_uri}
   - Redirects → https://meo.troioi.vn/gpt-connect
              ?session_id={sid}&session_sig={sig}

4. Main app /gpt-connect (React page):
   - Validates HMAC signature (proves request came from connector)
   - If logged in: shows consent screen "Connect your Meo Mai Moi account to ChatGPT?"
   - If not logged in: shows login form → after login → consent screen
   - If new user: shows registration form (no invite required for GPT flow) → consent

5. User confirms → main app frontend:
   - Calls POST /api/gpt-auth/confirm {session_id, session_sig}
   - Backend generates one-time auth_code (UUID, stored in Redis TTL 5 min: code → user_id)
   - Backend creates a Sanctum token with abilities:
         ["pet:read", "pet:write", "health:read", "health:write", "profile:read"]
     (`profile:read` is not used by connector endpoints in MVP but reserved for future user
     profile features; granting it now avoids forcing all users to reconnect later)
   - Stores: auth_code → {user_id, sanctum_token}
   - Returns: {redirect_url: "https://gpt.troioi.vn/oauth/callback?session_id=...&code=..."}
   - Frontend redirects browser to that URL

6. Connector /oauth/callback:
   - Looks up session_id in Redis → retrieves {state, redirect_uri}
   - Calls POST https://meo.troioi.vn/api/gpt-auth/exchange
         Authorization: Bearer {CONNECTOR_API_KEY}
         Body: {code}
   - Main app validates code (single use), returns {sanctum_token, user_id}
   - Connector deletes session from Redis
   - Connector generates short-lived auth_code_for_chatgpt (stored in Redis TTL 5 min)
   - Redirects → {redirect_uri}?code={auth_code_for_chatgpt}&state={state}

7. ChatGPT calls POST https://gpt.troioi.vn/oauth/token
   Body: {grant_type, code, client_id, client_secret}

8. Connector /oauth/token:
   - Validates client_id + client_secret
   - Looks up auth_code_for_chatgpt in Redis → gets sanctum_token
   - Deletes code from Redis (single use)
   - Issues JWT:
       {sub: user_id, tok: AES-256-GCM(sanctum_token, ENCRYPTION_KEY), iat, exp: +1y}
   - Signs JWT with connector's JWT_SECRET
   - Returns {access_token: jwt, token_type: "bearer", expires_in: 31536000}

9. ChatGPT stores JWT, includes in every action: Authorization: Bearer {jwt}

10. Connector on every action call:
    - Validates JWT signature
    - Decrypts sanctum_token from JWT payload
    - Forwards request to main app: Authorization: Bearer {sanctum_token}
```

### 4.2 New User Registration via GPT

When a visitor arrives at `/gpt-connect` without an account:
- Registration form is shown (name, email, password).
- Registration is processed by a dedicated endpoint `POST /api/gpt-auth/register` that does not
  require an invitation code (protected by the HMAC session signature instead).
- After registration, the user sees the consent screen immediately.
- A `registered_via_gpt: true` flag should be stored on the user record for analytics.
- The session_id is marked as `registration_attempted:{session_id}` in Redis (TTL 10 min)
  immediately after a registration call, preventing the same HMAC-signed session from being
  reused to create multiple accounts. This mirrors the `gpt_confirm_used:{session_id}` pattern
  used by the confirm endpoint.

### 4.3 Existing User Account Linking

If a user already has a Meo Mai Moi account:
- They arrive at `/gpt-connect`, log in if needed, and see the consent screen.
- This is the same flow as above — the "linking" is just creating a Sanctum token for the connector.
- A user can connect multiple GPT sessions; each creates its own Sanctum token.

### 4.4 Token Lifecycle

- **Connector JWT**: 1-year expiry. If it expires, ChatGPT will re-initiate the OAuth flow.
- **Sanctum token**: Long-lived (no expiry set). Revocable from the main app admin or user settings.
- **Revocation**: `POST /oauth/revoke` on the connector calls the main app to delete the Sanctum
  token. ChatGPT will be forced to re-authenticate on next use.

### 4.5 Security Controls

- All communication over HTTPS only.
- JWT signed with `HS256` + connector's `JWT_SECRET`.
- Sanctum token encrypted with `AES-256-GCM` + `ENCRYPTION_KEY` before embedding in JWT.
- `CONNECTOR_API_KEY` used for server-to-server calls (main app → connector is never needed;
  connector → main app for the exchange step).
- `HMAC_SHARED_SECRET` used to sign session redirects (prevents CSRF on the consent page).
  **HMAC validation is authoritative in the server-side Laravel controller only.** Any
  display of the consent page before the controller validates the signature is UX only.
  No security decision is made client-side.
- Rate limiting on all OAuth endpoints.
- No tokens, no PII in logs — only `user_id`, `request_id`, `endpoint`, `status`, `latency`.

### 4.6 Auth Failure Modes

What happens at each point in the OAuth flow when something goes wrong:

| Step | Failure | Connector behavior | User sees |
|---|---|---|---|
| `GET /oauth/authorize` | Invalid `client_id` | 400 HTML error page | "Invalid request" |
| `GET /oauth/authorize` | Redis unavailable | 503, abort | "Service temporarily unavailable" |
| `GET /oauth/callback` | `session_id` not in Redis (expired or never set) | HTML 400 error page: "Your session has expired. Please return to ChatGPT and start the connection again." Redirect is impossible — `redirect_uri` and `state` are stored inside the missing Redis key. | User sees error page; must restart from ChatGPT |
| `GET /oauth/callback` | Exchange call to main app fails (network) | redirect with `error=server_error` | ChatGPT: "Authorization failed" |
| `GET /oauth/callback` | Exchange call returns 401 (bad `CONNECTOR_API_KEY`) | redirect with `error=server_error` | operator must fix misconfiguration |
| `GET /oauth/callback` | Exchange call returns 400 (code expired/used) | redirect with `error=access_denied` | ChatGPT: "Authorization failed" |
| `POST /oauth/token` | Code not in Redis (expired, TTL 5 min) | 400 `{"error": "invalid_grant"}` | ChatGPT retries or re-initiates flow |
| `POST /oauth/token` | Wrong `client_secret` | 401 `{"error": "invalid_client"}` | operator must fix configuration |

**Redis unavailability during auth:** the connector fails fast and returns an appropriate
error redirect or HTTP error. There is no retry logic — the user is asked to try again.
In-flight OAuth sessions stored in Redis are lost on Redis restart; affected users must
restart the OAuth flow (acceptable given the 10-minute TTL).

**All failure redirects to `redirect_uri`** include `?error=...&state={state}` so ChatGPT
can display a message rather than hanging indefinitely.

---

## 5. API Surface (Connector)

All endpoints require `Authorization: Bearer {jwt}` except OAuth2 and health endpoints.

### 5.1 OAuth2 Endpoints

```
GET  /oauth/authorize     — Start OAuth2 flow (redirect to main app)
GET  /oauth/callback      — Return from main app, exchange code for Sanctum token
POST /oauth/token         — Exchange auth code for JWT (called by ChatGPT)
POST /oauth/revoke        — Revoke tokens (disconnect from ChatGPT)
GET  /health              — Liveness check {status: "ok", version: "..."}
```

### 5.2 Pet Endpoints

The connector exposes **semantic tools**, not REST mirrors. Some tools combine multiple main app
calls internally. The LLM sees clean, intent-oriented operations rather than raw CRUD.

```
GET    /pets              — List user's pets with optional name/species filter
POST   /pets/find         — Semantic search: find pets by name (fuzzy, returns candidates)
POST   /pets              — Create pet (includes internal duplicate check)
GET    /pets/{id}         — Get pet details with health summary
PATCH  /pets/{id}         — Update pet
GET    /pet-types         — List available pet types (cached, for species resolution)
```

**HTTP method translation**: The connector exposes `PATCH` for update endpoints (semantically
correct for partial updates from ChatGPT). Internally, it forwards `PUT` requests to the main
app, which uses `Route::put()`. Implementation must confirm the main app's update controllers
accept partial payloads (typical Laravel `$model->fill(request()->only([...]))->save()` does).

**POST /pets/find** (semantic search tool):
```json
{ "name": "Clauddy", "species": "cat" }
```
Internally calls `GET /api/my-pets`, applies filtering, returns ranked candidates. The LLM calls
this whenever the user refers to a pet by name and a confirmed ID is not already known. The tool
can return 0, 1, or multiple candidates — enabling the GPT to confirm with the user when ambiguous.

**POST /pets request schema (connector layer):**
```json
{
  "name": "Clauddy",
  "species": "cat",
  "sex": "female",
  "birth_date": "YYYY-MM-DD",
  "birth_month_year": "YYYY-MM",
  "age_months": 6,
  "description": "..."
}
```
Exactly one of `birth_date`, `birth_month_year`, or `age_months` should be provided (all optional).
Connector translates:
- `species` → looks up `pet_type_id` via cached `GET /pet-types`
- `sex: "unknown"` → maps to `"not_specified"` in the main app request (main app `PetSex` enum
  uses `not_specified`, not `unknown`; connector accepts the more natural `"unknown"` from GPT)
- `birth_date` → decomposes to `birthday_year`, `birthday_month`, `birthday_day`, `birthday_precision: "day"`
- `birth_month_year` → `birthday_year`, `birthday_month`, `birthday_precision: "month"`
- `age_months` → computes `birthday_year`, `birthday_month` from current date, `birthday_precision: "month"`

`POST /pets` also performs an internal duplicate check (calls `find` logic) before creating.
If a pet with the same name already exists, it returns a warning with the existing pet's details,
letting the GPT ask the user to confirm before proceeding.

### 5.3 Vaccination Endpoints

```
GET    /pets/{id}/vaccinations             — List vaccination records
POST   /pets/{id}/vaccinations             — Create vaccination record
PATCH  /pets/{id}/vaccinations/{vid}       — Update vaccination record
```

**POST /pets/{id}/vaccinations request schema:**
```json
{
  "vaccine_name": "Rabies",
  "administered_at": "YYYY-MM-DD",
  "due_at": "YYYY-MM-DD",
  "notes": "Extracted from certificate by ChatGPT"
}
```

Note: No binary file upload in MVP. GPT extracts data from uploaded photos/PDFs using vision.
The `notes` field can carry context like "data extracted from certificate image by ChatGPT".

### 5.4 Medical Record Endpoints

```
GET    /pets/{id}/medical-records          — List medical records
POST   /pets/{id}/medical-records          — Create medical record
PATCH  /pets/{id}/medical-records/{rid}    — Update medical record
```

**POST /pets/{id}/medical-records request schema:**
```json
{
  "record_type": "deworming",
  "description": "Dewormed 2 months ago",
  "record_date": "YYYY-MM-DD",
  "vet_name": "Dr. Nguyen"
}
```

Canonical `record_type` values (the authoritative list — used in OpenAPI enum, GPT system prompt,
and connector validation):
`checkup`, `deworming`, `flea_treatment`, `surgery`, `dental`, `other`.

The connector defaults `record_type` to `"other"` if the value provided by the GPT doesn't match
a known type. This prevents any unexpected value from reaching the main app while still allowing
the GPT to supply a best-effort type from the examples.

### 5.5 Weight Endpoints

```
GET    /pets/{id}/weights                  — Get weight history
POST   /pets/{id}/weights                  — Add a single weight record
```

**POST /pets/{id}/weights request schema:**
```json
{
  "weight_kg": 3.2,
  "measured_at": "YYYY-MM-DD"
}
```

Field mapping: `measured_at` (connector API, human-friendly) maps to `record_date` in the main
app request (`WeightHistory` model uses `record_date`).

Bulk weight entry (from photo): GPT calls `GET /pets` to resolve names to IDs, then calls
`POST /pets/{id}/weights` once per pet. No special bulk endpoint needed — GPT orchestrates it.

### 5.6 Error Shape (Standardized)

All non-2xx responses use this shape:

```json
{
  "error": "VALIDATION_ERROR",
  "message": "birth_date must be in YYYY-MM-DD format",
  "fields": [{"name": "birth_date", "reason": "invalid_format"}],
  "request_id": "req_abc123"
}
```

Standard error codes:
- `VALIDATION_ERROR` — bad input, GPT should ask user to correct
- `NOT_FOUND` — pet/record doesn't exist
- `UNAUTHORIZED` — token invalid or expired; GPT should prompt user to reconnect
- `AMBIGUOUS` — multiple matches, GPT should disambiguate
- `UPSTREAM_ERROR` — main app returned unexpected error; GPT should suggest retrying
- `DUPLICATE_WARNING` — a record with the same name already exists; returned (HTTP 409) instead
  of creating; includes existing record details; GPT must confirm with user before retrying with
  `confirm_duplicate: true`

**Upstream 429 handling**: if the main app returns HTTP 429 (rate limit), the connector translates
it to `UPSTREAM_ERROR` with message "The server is busy, please try again in a moment." The GPT's
existing `UPSTREAM_ERROR` handling (suggest retry) is appropriate for this case.

---

## 6. File Handling Strategy

**MVP: no binary file passthrough.**

When a user uploads a photo or PDF to the ChatGPT conversation:
1. The GPT uses its vision capability to read the document.
2. The GPT extracts structured data (dates, vaccine names, vet info, weights).
3. The GPT calls the connector with structured JSON — no file URL involved.

This is cleaner than downloading from OpenAI's CDN and re-uploading, and it works for PDFs too
(which the main app doesn't currently support as uploads).

**Phase 2 consideration:** If users want the original file stored, we would:
- Have the connector download from the temporary OpenAI CDN URL.
- Re-upload to the main app via the existing photo endpoint.
- Require extending the main app to accept PDFs (update MIME type list in MediaLibrary collection).

---

## 7. OpenAPI Design for LLM Compatibility

FastAPI auto-generates the OpenAPI schema from Pydantic models. Key rules:

1. **Descriptions are instructions**: Every field and endpoint description is read by the GPT to
   decide when and how to call the tool. Write them as clear directives.

2. **No ambiguous optional overloads**: If a field has complex logic, break it into separate named
   fields (e.g., `birth_date`, `birth_month_year`, `age_months` — not one polymorphic field).

3. **Enums over strings where possible**: Use string literals in OpenAPI enum to constrain GPT input.
   Example: `sex: "male" | "female" | "unknown"`.

4. **Stable IDs in responses**: Always include the backend `id` in responses so GPT can use it in
   follow-up calls without needing to re-query.

5. **Return disambiguators**: If a GET returns multiple items, include enough fields for the GPT to
   let the user confirm the right one (name, species, age, sex).

6. **Prefer 200 with structured body over 4xx for GPT-recoverable situations**: Validation errors
   that the GPT can act on should still have a structured 422 body. True 5xx means connector failure.

---

## 8. Conversational Reliability Rules

1. **Missing required fields** → return precise validation errors per field.
2. **Ambiguous pet identification** (e.g., user says "my cat" when they have 3 cats) → GPT calls
   `POST /pets/find` which returns candidates. GPT presents them to the user for confirmation.
   This logic lives in the connector, not in the GPT's reasoning.
3. **Duplicate prevention**: `POST /pets` internally runs the find logic before creating. If a
   pet with the same name exists, the connector returns the existing pet with a `DUPLICATE_WARNING`
   so the GPT can ask "You already have a cat named Clauddy — did you mean her?". The write only
   proceeds if the GPT makes a second call with `{"confirm_duplicate": true}`.
4. **Revocation handling**: If the main app returns 401 (Sanctum token revoked), the connector
   translates this to `UNAUTHORIZED` with message "Your connection has been revoked. Please
   reconnect via ChatGPT." ChatGPT will re-initiate the OAuth flow. This is the complete
   revocation story — no proactive checking needed for what is an edge case.
5. **Concise success payloads**: Return only the fields the GPT needs for confirmation + follow-up.
6. **No hallucination in errors**: If the main app returns an unexpected error, the connector returns
   `UPSTREAM_ERROR` with a safe user-facing message, never exposing stack traces.

---

## 9. Main App Integration Points

See `../meo-mai-moi/tmp/gpt-connector-plan.md` for the full change list.

**Main app response envelope**: the main app wraps all API responses in
`{"success": true, "data": {...}, "message": "..."}` (via `ApiResponseTrait`). The connector
unwraps the `data` field before building its own response to ChatGPT. Error responses from the
main app (non-2xx) are translated to the connector's error shape — the main app's `message`
field may be included in the connector's `message` field for debugging context.

Summary of changes needed in `meo-mai-moi`:

1. **New web page**: `GET /gpt-connect` — OAuth consent + login + optional registration.
2. **New API endpoint**: `POST /api/gpt-auth/confirm` — creates one-time auth code + Sanctum token.
3. **New API endpoint**: `POST /api/gpt-auth/exchange` — server-to-server code-for-token exchange.
4. **New API endpoint**: `POST /api/gpt-auth/register` — registration without invite code (protected
   by HMAC session signature).
5. **Config**: `GPT_CONNECTOR_API_KEY`, `GPT_CONNECTOR_HMAC_SECRET`, `GPT_CONNECTOR_URL`.
6. **Optional**: `registered_via_gpt` boolean column on `users` table for analytics.

---

## 10. Deployment & Ops

### Container setup

- Single Docker container for the connector.
- Redis as a sidecar (or shared Redis if main app already has one in the stack).

### Environment variables

```
# Main app connection
MAIN_APP_URL=https://meo.troioi.vn
CONNECTOR_API_KEY=...          # Sent to main app for server-to-server calls

# OAuth2 config
OAUTH_CLIENT_ID=meo-gpt
OAUTH_CLIENT_SECRET=...        # Checked when ChatGPT calls /oauth/token

# Security
JWT_SECRET=...                 # Signs connector JWTs
ENCRYPTION_KEY=...             # AES-256-GCM key for Sanctum token in JWT
HMAC_SHARED_SECRET=...         # Shared with main app for consent page HMAC

# Redis
REDIS_URL=redis://localhost:6379

# Ops
LOG_LEVEL=info
RATE_LIMIT_PER_MINUTE=60
ENVIRONMENT=production
```

### Observability

Structured JSON log fields on every request:
```json
{"request_id": "...", "endpoint": "POST /pets", "user_id": 42, "status": 201, "latency_ms": 85}
```

### Alerting baseline

- High 5xx rate (>5% over 5 min window).
- Auth failure spike (>20 failures/min).
- Latency p95 > 2000ms.

### Readiness/liveness

- `GET /health` always returns **HTTP 200** with `{status: "ok", version: "...", main_app_reachable: true/false}`.
  When the main app is down, `main_app_reachable` is `false` but the HTTP status remains 200 —
  the connector itself is healthy and can still handle OAuth and token validation. Monitoring
  systems should inspect the body, not just the status code.
- Main app reachability check: lightweight `GET /api/version` call (or equivalent ping endpoint).

### Key rotation

Rotating secret values has user-visible impact:

| Key | Impact of rotation | Recovery |
|---|---|---|
| `ENCRYPTION_KEY` | All existing connector JWTs fail decryption. Every GPT user must reconnect (re-run OAuth flow). | Plan for low-traffic window. No data is lost — only re-auth is required. |
| `JWT_SECRET` | Same as `ENCRYPTION_KEY` — all JWTs become invalid. | Same as above. |
| `HMAC_SHARED_SECRET` | In-flight OAuth sessions (Redis, TTL 10 min) become unverifiable. Brief auth disruption only. | Any user mid-auth-flow must restart. Impact < 10 minutes. |
| `CONNECTOR_API_KEY` | Server-to-server exchange calls fail. No user-visible impact if rotated atomically. | Must be updated in connector and main app simultaneously. |

---

## 11. Phase Plan

### Phase 0 — Infrastructure (before first feature)
Set up repo, FastAPI skeleton, Docker, Redis, logging, CI.

### Phase 1 — Authentication
OAuth2 flow end-to-end. Main app consent page. New user registration. Token issuance.
This is the critical path blocker for everything else.

### Phase 2 — Core Read/Write
Pet list, detail, create, update. Vaccination records. Medical records. Weight records.
End-to-end test: create a full pet profile through ChatGPT.

### Phase 3 — GPT Integration
OpenAPI spec review for GPT compatibility. Create Custom GPT in OpenAI. Configure actions.
Write GPT system prompt. Test full conversation flows.

### Phase 4 — Hardening
Rate limiting, idempotency guards, error taxonomy, observability. Load test.

### Phase 5 — Enhancements (post-launch)
Binary file passthrough (PDF + image upload). Computed smart query endpoints (e.g., "pets with
vaccination due in N days" as a single optimized endpoint rather than client-side filter).
Zalo OA integration (if desired — reuses connector service logic).

---

## 12. Open Questions / Validation Needed

1. Does the main app's Sanctum configuration support token abilities/scopes? If not, scope
   enforcement lives only in the connector for now (acceptable for MVP).
2. The main app's rate limit for `POST /pets` is 10/min — confirm this is sufficient for GPT
   usage patterns (GPT can generate bursts during complex pet creation flows).
3. Does `GET /api/my-pets` support any filtering params (name, species)? **Decision**: the
   connector's `find` tool does client-side filtering on the full list returned by the main app.
   This is acceptable for typical pet counts per user. If the main app adds `?name=` param later,
   the connector can optionally use it as a pre-filter, but the connector-side filtering stays
   regardless (for ranking and disambiguation).
