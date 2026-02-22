# 03 - OAuth Endpoints (Connector)

**Goal:** Provide the `/oauth` endpoints necessary for ChatGPT to connect via Authorization Code Flow.

## Definition of Done

- ChatGPT (or mock test) can run through the `authorize -> callback -> token` loop successfully.
- Redis safely tracks OAuth flow state.
- Revocation functionality is drafted.
- End-to-end unit/integration tests confirming OAuth failures and successes.

## Implementation Steps

1. **GET `/oauth/authorize`:**
   - Validate `client_id`, `response_type`, and `redirect_uri` against Settings.
   - Generate `session_id` (uuid).
   - Generate an HMAC-SHA256 signature of `session_id` using `HMAC_SHARED_SECRET`.
   - Store session context `{state, redirect_uri}` in Redis (`oauth:session:{session_id}`) with 10m TTL.
   - Return 302 Redirect to `{MAIN_APP_URL}/gpt-connect?session_id={session_id}&session_sig={hmac_sig}`.
   - Handle missing/invalid inputs (return 400).
2. **GET `/oauth/callback`:**
   - Accepts `session_id` and `code` (created by main app).
   - Looks up `session_id` in Redis. If missing/expired, directly return a `400 Bad Request` HTML error telling user to retry.
   - Calls `POST {MAIN_APP_URL}/api/gpt-auth/exchange` using `Bearer CONNECTOR_API_KEY`, sending `{code}`.
   - Main app responds with `{sanctum_token, user_id}`.
   - Delete `session_id` from Redis.
   - Generate `chatgpt_auth_code` (UUID), store token+user info in Redis TTL 5m.
   - Return 302 Redirect back to ChatGPT's original `redirect_uri?code={chatgpt_auth_code}&state={state}`.

3. **POST `/oauth/token`:**
   - Accepts standard form data (`python-multipart` required): `client_id`, `client_secret`, `grant_type="authorization_code"`, `code`.
   - Fast fail invalid client configs.
   - Atomically `get_and_delete` the code from Redis.
   - Issue a JWT (using `core/jwt.py`) encrypting the `sanctum_token`.
   - Return exactly: `{"access_token": "...", "token_type": "bearer", "expires_in": 31536000}`.

4. **POST `/oauth/revoke`:**
   - Extracts JWT `tok`.
   - Calls `POST {MAIN_APP_URL}/api/gpt-auth/revoke` via `CONNECTOR_API_KEY` with `{token: sanctum_token}`. (Assuming main app implements it).

5. **Auth Middleware / Dependency:**
   - Create a FastAPI Dependency `get_current_token` that requires an `Authorization: Bearer <jwt>`, validates it via `core/jwt.py`, and returns downstream state so other routes can use `<sanctum_token>`.

6. **Tests:**
   - `test_auth_flow.py`: Emulate exactly this process.
