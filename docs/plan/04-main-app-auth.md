# 04 - Main App Authority Configuration

**Goal:** Modify the core Meo Mai Moi Laravel backend to authorize the GPT connector. Since this runs on `meo-mai-moi`, instructions are specifically for that repository context.

## Definition of Done

- `POST /api/gpt-auth/confirm`, `POST /api/gpt-auth/exchange`, `POST /api/gpt-auth/register`, and `POST /api/gpt-auth/revoke` (if implemented).
- `GET /gpt-connect` React UI running successfully.
- `registered_via_gpt` column on users table.

## Implementation Steps for Main App

**(Note: If the agent is only touching connector repo, skip this stage and manually request main app updates, verifying they exist via HTTP checks).**

1. **Config Additions (`config/services.php`):**
   - Add `gpt_connector` config with keys `url`, `api_key`, `hmac_secret`. Read from `.env`.

2. **Migration:**
   - Create migration to add `boolean('registered_via_gpt')->default(false)` strictly for tracking.

3. **API Endpoint Route Handlers (`routes/api.php` \& Controllers):**
   - **`/confirm`**: Validates HMAC signature over `session_id`. Creates a Sanctum token (`auth()->user()->createToken('gpt-connector', abilities...)`). Stashes token id to Redis tied to a generated one-time `auth_code`. Returns redirect URL back to connector.
   - **`/exchange`**: Protected by custom `CONNECTOR_API_KEY` Bearer check. Receives `code`, looks up Redis, returns `sanctum_token` and `user_id`.
   - **`/register`**: Open endpoint. Validates HMAC, creates a user without requiring system-invite logic, logs in user, returns auth JSON.
   - **`/revoke`**: Optional (Added during QA). Deletes token string sent in JSON body.

4. **React Frontend (`/gpt-connect`):**
   - Shows consent screen to logged-in users.
   - Shows Login if not authenticated.
   - Shows minimal Register form if they decide to sign up.
   - Posts to `/confirm` once agreed. Redirects browser directly afterwards.
