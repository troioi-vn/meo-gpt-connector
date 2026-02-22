# 07 - Admin Interface

**Goal:** Implement a minimal, stateless, HTMX-powered dashboard specifically for developers to monitor GPT interactions in development/staging. Disabled in prod.

## Definition of Done

- Router path `GET /admin/*` locked via HTTP Basic Auth.
- Disabled via env var `ADMIN_ENABLED=false` (Returning HTTP 404).
- Request events appended to a Redis sorted set (`ZADD` + trimmed to last 1000).
- Minimal `jinja2` HTMX page visualizing last 50 queries and any errors.

## Implementation Steps

1. **Admin Events Manager (`src/core/admin_events.py`):**
   - `append_event(event: dict)`: Pushes a serialized JSON dict into `admin:events` sorted set. Score = timestamp. Trims everything past rank 1000.
   - `get_recent(n: int, errors_only: bool)` returns the top `N` elements via `ZREVRANGE`.
   - Add this appending script sequentially at the end of the main FastAPI request middleware so every response (OAuth + Actions) pushes an event:
     `{"request_id": "req_...", "ts": 170..., "method": "POST", "path": "/pets", "user_id": 42, "status": 201, "latency_ms": 85, "error_code": null}`

2. **Basic Auth Dependency:**
   - Use FastAPI's HTTPBasic. Hardcode username `"admin"`.
   - Check against `ADMIN_PASSWORD`. Return HTTP 401 if failed.
   - Return 404 altogether if `ADMIN_ENABLED=false`.
3. **Templates (`src/templates/admin/`):**
   - Wire `Jinja2Templates` to FastAPI.
   - `base.html`: HTML5 wrapper + CDN links to HTMX.
   - `index.html`: Polling structure `<div hx-get="/admin/partials/requests" hx-trigger="every 5s">`.
   - `partials/stats.html`, `partials/requests.html`, `partials/errors.html` containing only standard HTML table fragments.
4. **Router (`src/routers/admin.py`):**
   - **`GET /admin/`** Renders full `index.html`.
   - **`GET /admin/partials/requests`** Returns `requests.html` populated by top 50 rows.
   - **`GET /admin/partials/errors`** Returns `errors.html` populated by top 20 rows containing `status >= 400`.
   - **`GET /admin/partials/stats`** Scans active `oauth:session:*` keys and simple statistics.
