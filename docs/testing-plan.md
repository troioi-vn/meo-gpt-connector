# Testing Plan

## Strategy

Two test types:

1. **Unit tests** — cover the connector's own logic in isolation, with mocked HTTP calls.
   No Docker, no running services. Fast enough to run on every save.
2. **Integration tests** — run the connector against a real Meo Mai Moi instance
   running locally in Docker. Validate end-to-end behavior against a live API.

Unit tests run in CI on every push. Integration tests run locally on demand and as
a pre-merge gate on `dev → main`.

---

## Directory Structure

```
tests/
├── conftest.py                   # Shared: settings override, JWT factory helper
├── unit/
│   ├── test_jwt.py               # Issue, validate, expire, tamper
│   ├── test_crypto.py            # Encrypt/decrypt round-trip, tamper detection
│   ├── test_normalization.py     # Input → main app schema translation
│   ├── test_duplicate_filter.py  # find filtering: 0 / 1 / N results
│   └── test_error_translation.py # Main app HTTP status → connector error code
└── integration/
    ├── conftest.py               # Docker readiness, test user, JWT fixture
    ├── test_auth_flow.py         # OAuth2 end-to-end (authorize → token)
    ├── test_pets.py              # CRUD + find + duplicate check
    ├── test_vaccinations.py
    ├── test_medical_records.py
    └── test_weights.py
```

---

## Dependencies

```toml
# pyproject.toml [tool.pytest...]
[project.optional-dependencies]
test = [
    "pytest",
    "pytest-asyncio",
    "respx",          # mock httpx calls in unit tests
    "pytest-cov",     # coverage reporting
    "httpx",          # async test client for integration tests
]
```

`respx` is the key tool for unit tests — it intercepts `httpx` calls and returns
canned responses without any network activity.

---

## Unit Tests

Unit tests import functions directly from `src/`. No HTTP server is started.

### `test_jwt.py`

Tests `core/jwt.py` — issue and validate JWTs.

| Test | Input | Expected |
|---|---|---|
| Round-trip | valid payload | decoded payload matches original |
| Expired | JWT with `exp` in past | `ExpiredSignatureError` |
| Wrong secret | JWT signed with different key | `JWTError` |
| Tampered payload | modified `sub` field | `JWTError` |
| Missing `sub` | no `sub` in payload | `JWTError` |
| Missing `tok` | no encrypted token in payload | `JWTError` |

### `test_crypto.py`

Tests `core/crypto.py` — AES-256-GCM encrypt/decrypt.

| Test | Input | Expected |
|---|---|---|
| Round-trip | arbitrary string | `decrypt(encrypt(s)) == s` |
| Nonce uniqueness | same plaintext twice | ciphertexts differ |
| Tampered ciphertext | flip one byte | raises `InvalidTag` or `ValueError` |
| Wrong key | decrypt with different key | raises error |
| Empty string | `""` | round-trip succeeds |
| Long string | 4 KB string | round-trip succeeds |

### `test_normalization.py`

Tests the pet input schema → main app schema translation. These functions live in the
pets router or a shared `services/normalization.py`.

| Test | Input | Expected main app fields |
|---|---|---|
| `birth_date` | `"2024-08-15"` | `birthday_day=15, birthday_month=8, birthday_year=2024, birthday_precision="day"` |
| `birth_month_year` | `"2024-08"` | `birthday_year=2024, birthday_month=8, birthday_precision="month"` |
| `age_months: 6` | `6` months ago from test date | correct year/month, `precision="month"` |
| No date fields | none provided | all birthday fields absent |
| `species: "cat"` | cached types contain cat | resolves to correct `pet_type_id` |
| `species: "dragon"` | not in cached types | `VALIDATION_ERROR` |
| `birth_date` + `age_months` | both provided | `VALIDATION_ERROR` (ambiguous) |
| `sex: "female"` | valid enum value | passes through |
| `sex: "maybe"` | invalid | `VALIDATION_ERROR` |

### `test_duplicate_filter.py`

Tests the filtering logic shared by `POST /pets/find` and the internal duplicate check
in `POST /pets`. Given a list of pet objects from the main app, apply name/species filter.

| Test | Pet list | Query | Expected |
|---|---|---|---|
| Exact match | `[{name:"Mimi", species:"cat"}]` | `name="Mimi"` | 1 result |
| Case-insensitive | `[{name:"Mimi"}]` | `name="mimi"` | 1 result |
| No match | `[{name:"Coco"}]` | `name="Mimi"` | 0 results |
| Partial match ignored | `[{name:"Mimiko"}]` | `name="Mimi"` | 0 results (exact only) |
| Multiple name matches | `[Mimi(cat), Mimi(dog)]` | `name="Mimi"` | 2 results |
| Species filter narrows | `[Mimi(cat), Mimi(dog)]` | `name="Mimi", species="cat"` | 1 result |
| Empty list | `[]` | any | 0 results |

### `test_error_translation.py`

Tests that `services/main_app.py` translates main app HTTP responses to connector error
shapes. Uses `respx` to return canned responses.

| Main app HTTP response | Expected connector error code | Expected HTTP status |
|---|---|---|
| 404 `{"message": "Not found"}` | `NOT_FOUND` | 404 |
| 422 with `errors` dict | `VALIDATION_ERROR` with `fields` | 422 |
| 401 | `UNAUTHORIZED` | 401 |
| 429 | `UPSTREAM_ERROR` | 502 |
| 500 | `UPSTREAM_ERROR` | 502 |
| network timeout (httpx.TimeoutException) | `UPSTREAM_ERROR` | 502 |
| connection refused | `UPSTREAM_ERROR` | 502 |

---

## Integration Tests

### Setup assumption

Integration tests assume **meo-mai-moi is already running locally** (developer starts it
separately). The connector is started by the test suite itself (or can already be running).

The integration conftest checks reachability before running any test and fails fast if the
main app is down.

**To run:**

```bash
# Terminal 1: start meo-mai-moi (in the meo-mai-moi repo)
docker compose up

# Terminal 2: run integration tests
MAIN_APP_URL=http://localhost:80 pytest tests/integration/ -v
```

Convenience script in `scripts/test-integration.sh` wraps this.

### Fixture chain (`tests/integration/conftest.py`)

```
scope=session:
  main_app_reachable  — GET /api/version → 200, fail immediately if not
  connector_running   — GET /health → {main_app_reachable: true}
  test_user           — create via docker exec artisan tinker (or seeder)
  sanctum_token       — POST /api/login with test user credentials
  auth_jwt            — wrap sanctum_token in connector JWT (bypass OAuth flow)
  client              — httpx.AsyncClient(base_url="http://localhost:8001",
                          headers={"Authorization": f"Bearer {auth_jwt}"})

scope=function:
  clean_pets          — delete any pets created during the test (yield fixture)
```

The `auth_jwt` fixture **bypasses the OAuth browser flow** entirely. This is fine for
integration tests — the OAuth flow is tested separately in `test_auth_flow.py`.

### `test_auth_flow.py`

Simulates the OAuth2 flow using httpx following redirects manually:

```
1. GET /oauth/authorize → 302 to main app /gpt-connect?session_id=...&session_sig=...
   Assert: session_id in Redis, sig is valid HMAC

2. Simulate confirm: POST /api/gpt-auth/confirm {session_id, session_sig}
   Assert: returns {redirect_url} containing auth code

3. GET /oauth/callback?session_id=...&code=...
   Assert: 302 to mock redirect_uri with code parameter

4. POST /oauth/token {grant_type=authorization_code, code, client_id, client_secret}
   Assert: returns {access_token, token_type: "bearer", expires_in: 31536000}

5. GET /pets with returned JWT
   Assert: 200 (valid auth works)
```

New user path:

```
6. GET /oauth/authorize → redirect → arrive at /gpt-connect unauthenticated
7. POST /api/gpt-auth/register {email, password, name, session_id, session_sig}
   Assert: 201, user created with registered_via_gpt=true
8. Continue from step 2 above
```

### `test_pets.py`

| Test | What it does | Assert |
|---|---|---|
| List pets (empty) | `GET /pets` | 200, empty list |
| Create (full date) | `POST /pets` with `birth_date` | 201, pet ID in response |
| Create (age_months) | `POST /pets` with `age_months=6` | 201; verify precision="month" in main app |
| Create (month_year) | `POST /pets` with `birth_month_year="2024-08"` | 201; verify precision="month" |
| Create (no date) | `POST /pets` no date fields | 201, no birthday stored |
| Duplicate warning | Create pet, then create same name again | second call: `DUPLICATE_WARNING` returned |
| Confirm duplicate | Repeat with `confirm_duplicate: true` | 201, second pet created |
| Find — match | `POST /pets/find {name: "Mimi"}` | returns matching candidate |
| Find — no match | `POST /pets/find {name: "Nobody"}` | 200, empty candidates list |
| Find — ambiguous | Two pets named "Mimi", query "Mimi" | 200, two candidates |
| Species filter | `POST /pets/find {name:"Mimi", species:"cat"}` | only cat Mimi returned |
| Get detail | `GET /pets/{id}` | 200, full pet data including health summary |
| Update | `PATCH /pets/{id} {name:"NewName"}` | 200, updated name in response |
| Unknown species | `POST /pets` with `species:"dragon"` | 422 `VALIDATION_ERROR` |

### `test_vaccinations.py`

| Test | Assert |
|---|---|
| `POST /pets/{id}/vaccinations` full fields | 201 |
| `GET /pets/{id}/vaccinations` | 200, contains created record |
| `PATCH /pets/{id}/vaccinations/{vid}` | 200, updated |
| POST without `vaccine_name` | 422 `VALIDATION_ERROR` |
| POST without `administered_at` | 422 `VALIDATION_ERROR` |

### `test_medical_records.py`

| Test | Assert |
|---|---|
| POST with `record_type="deworming"` | 201 |
| POST with `record_type="mystery_type"` | 201; verify stored as `"other"` |
| POST with `record_type="other"` | 201 |
| GET list | 200, records in order |
| PATCH | 200, updated |
| POST without `description` | 422 `VALIDATION_ERROR` |

### `test_weights.py`

| Test | Assert |
|---|---|
| `POST /pets/{id}/weights {weight_kg, measured_at}` | 201 |
| `GET /pets/{id}/weights` | 200, list in order |
| POST without `weight_kg` | 422 `VALIDATION_ERROR` |
| POST with `weight_kg=0` | 422 `VALIDATION_ERROR` (must be positive) |
| POST with `weight_kg=50.5` | 201 (boundary case) |

---

## Coverage Targets

| Module | Target | Rationale |
|---|---|---|
| `core/jwt.py` | 100% | Security-critical path |
| `core/crypto.py` | 100% | Security-critical path |
| Input normalization | 100% | Every translation path must be verified |
| `services/main_app.py` (error handling) | 95%+ | All error codes must be covered |
| Router handlers | 80%+ | Happy path + main error paths |
| Integration tests | N/A | Coverage here is about flow correctness, not line count |

---

## What is NOT tested here

- **GPT reasoning behavior**: tested manually in Phase 3 by running real GPT conversations.
- **Main app domain logic**: tested in meo-mai-moi's own test suite.
- **Load / performance**: Phase 4 task, using `k6` or `locust`.
- **HMAC validation of consent page redirect**: covered as a side effect of `test_auth_flow.py`.
- **Redis unavailability**: unit test with mocked Redis returning errors — add to `test_auth_flow.py`
  unit coverage for the failure path handling.

---

## Manual GPT action simulation

When debugging a real local stack, run a deterministic post-auth simulation script:

```bash
python scripts/simulate_gpt_tool_flow.py \
   --sanctum-token "<user_sanctum_token>" \
   --user-id <user_id>
```

The script emits a JSON trace with per-step status and response snippets for:
- `create_pet` (with automatic fallback seed if upstream requires extra fields),
- `find_pet`,
- `update_pet`,
- `add_weight`,
- `add_vaccination`,
- `add_medical_record`,
- list endpoints for weights/vaccinations/medical records.

For full OAuth bridge verification, run:

```bash
python scripts/simulate_oauth_flow.py \
   --sanctum-token "<user_sanctum_token>" \
   --verify-tools
```

This validates `authorize -> confirm -> callback -> token` and confirms the issued token can call connector tools.
