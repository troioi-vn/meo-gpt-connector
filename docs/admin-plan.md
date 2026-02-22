# Admin Interface Plan

## Purpose

A minimal development dashboard to see what's happening inside the connector:

- **Recent tool calls** — which endpoints the GPT is calling, with status and latency
- **Recent errors** — non-2xx responses with error codes
- **Active OAuth sessions** — how many auth flows are currently in progress

This is a **development and staging tool only**. It is disabled in production via an env var.

---

## Design Decisions

| Concern | Choice | Rationale |
|---|---|---|
| UI | HTMX + Jinja2 + plain CSS | No build step; FastAPI supports Jinja2 natively |
| Auth | HTTP Basic Auth, single password | Simple enough for a dev tool |
| Event storage | Redis sorted set, score = timestamp | Redis is already in the stack; no extra db |
| Event retention | Last 1000 events, trimmed on every write | Dev tool; no persistence requirement |
| Auto-refresh | HTMX polling every 5 seconds | Live view without WebSockets |
| Disabled state | Routes return 404 (not 401) | Doesn't reveal admin existence in production |

---

## New Environment Variables

```
ADMIN_ENABLED=true      # false → all /admin/* routes return 404
ADMIN_PASSWORD=...      # Required when ADMIN_ENABLED=true; startup fails if missing+enabled
```

---

## What Gets Logged

Every request through the connector's middleware appends a compact event to Redis:

```json
{
  "request_id": "req_abc123",
  "ts": 1708000000.0,
  "method": "POST",
  "path": "/pets",
  "user_id": 42,
  "status": 201,
  "latency_ms": 85,
  "error_code": null
}
```

Stored in Redis sorted set `admin:events`, score = timestamp.
Trim on every write: keep last 1000 (`ZREMRANGEBYRANK admin:events 0 -1001`).

`user_id` is `null` for OAuth flow requests (no JWT exists yet at that point).
No request body, no Sanctum tokens, no PII beyond user_id — consistent with the
"no tokens in logs" rule.

---

## Routes

```
GET  /admin/                      → full dashboard page (HTML)
GET  /admin/partials/requests     → recent requests table (HTMX partial, returns HTML)
GET  /admin/partials/errors       → recent errors table (HTMX partial, returns HTML)
GET  /admin/partials/stats        → stats bar (HTMX partial, returns HTML)
```

All `/admin/*` routes require HTTP Basic Auth (`admin` / `ADMIN_PASSWORD`).
Partials return HTML fragments only — no full page layout.

---

## Dashboard Layout

```
┌────────────────────────────────────────────────────────────────┐
│  meo-gpt-connector  v0.1.0  [development]                      │
├────────────────────────────────────────────────────────────────┤
│  Active OAuth sessions: 2       Uptime: 3h 22m                 │
│  Last 1h: 47 calls   12 errors         [auto-refreshes 5s]     │
├──────────────────────────┬─────────────────────────────────────┤
│  Recent requests (50)    │  Recent errors (20)                 │
│  [auto-refreshes 5s]     │  [auto-refreshes 5s]               │
│  ──────────────────────  │  ─────────────────────────────────  │
│  12:31  POST /pets   201 │  12:28  POST /pets  422 VALIDATION  │
│  12:31  GET  /pets   200 │  12:15  GET  /pets/99  404 NOT_FOUND│
│  12:30  POST /pets   201 │  11:58  POST /vacc  502 UPSTREAM    │
│  12:29  GET  /health 200 │                                     │
│  ...                     │  ...                                │
└──────────────────────────┴─────────────────────────────────────┘
```

Status codes ≥ 400 are highlighted in red. Latency > 1000ms highlighted in yellow.

---

## Implementation Structure

New files added to the existing project structure:

```
src/
├── routers/
│   └── admin.py                  # /admin/* route handlers
├── templates/
│   └── admin/
│       ├── base.html             # layout: version, env badge, nav
│       ├── index.html            # full dashboard page (loads partials)
│       └── partials/
│           ├── stats.html        # stats bar fragment
│           ├── requests.html     # recent requests table fragment
│           └── errors.html       # recent errors table fragment
└── core/
    └── admin_events.py           # write/read admin events in Redis
```

New dependencies:

```
jinja2            # FastAPI supports this; may already be in the dependency tree
python-multipart  # required for FastAPI form handling
```

No new database. No JavaScript framework. No build step.

---

## Auth Mechanism

HTTP Basic Auth middleware on all `/admin/*` paths:

- Check `Authorization: Basic {base64("admin:{ADMIN_PASSWORD}")}` header on every request.
- If missing or wrong → `401 WWW-Authenticate: Basic realm="meo-gpt-connector admin"`.
- If correct → pass through.

No session cookies. Browser caches Basic Auth credentials per origin, so the developer
only enters the password once per browser session.

Fixed username: `admin`. Only the password is configurable.

---

## Dashboard Data Sources

### Stats bar

- **Active OAuth sessions**: count of `oauth:session:*` keys in Redis
  (`KEYS oauth:session:*` count, or use a counter key updated on create/delete)
- **Calls in last hour**: `ZRANGEBYSCORE admin:events {now-3600} +inf` → count
- **Errors in last hour**: same range, filter events where `status >= 400`
- **Uptime**: computed from process start time (stored in memory at startup)

### Recent requests table

- `ZREVRANGE admin:events 0 49` → last 50 events, newest first
- Columns: time (HH:MM:SS), method, path, user_id (or `—`), status, latency_ms
- Red row if status ≥ 400, yellow cell if latency_ms > 1000

### Recent errors table

- `ZREVRANGE admin:events 0 499` → filter to status ≥ 400, take first 20
- Columns: time, path, status, error_code, user_id

---

## "Chats" vs Tool Calls

The connector has no concept of a chat session — it sees individual HTTP requests.
A "chat" in ChatGPT terms is a sequence of tool calls from the same user over time.

For the MVP admin, **chats are not tracked as sessions**. The recent requests table shows
individual tool calls. A developer can trace a user's activity by filtering by `user_id`.

If grouping becomes useful later, we could segment by `user_id + rolling 30-minute windows`,
but this adds complexity that isn't warranted for a dev tool.

---

## Limitations by Design

- **No request body logging**: bodies are never stored (Sanctum token safety). The admin shows
  what was called, not what was sent.
- **No persistent history**: Redis with 1000-event cap. Events survive connector restarts
  (Redis persists), but a Redis flush clears everything. Acceptable for a dev tool.
- **No production use**: Admin is disabled in production via `ADMIN_ENABLED=false`.
  If needed for a one-off production debug session: enable temporarily, rotate `ADMIN_PASSWORD`
  after, then disable.
- **Single-user**: Basic Auth with one password. Not designed for team access control.
