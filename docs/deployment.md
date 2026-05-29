# Deployment Guide

This guide describes the reusable deployment shape for `meo-gpt-connector`.
Environment-specific hostnames, SSH targets, server paths, DNS records, and live
operations should live outside this public repository.

For local development setup, see [install.md](install.md).

## Architecture

```text
Internet -> reverse proxy -> connector container -> Redis
                                      |
                                      v
                              main app API
```

The repository ships a Docker Compose setup with:

- the FastAPI connector
- a Redis sidecar for short-lived OAuth state
- configurable host ports through environment variables

## Prerequisites

- Docker and Docker Compose
- a reverse proxy such as nginx, Caddy, Traefik, or a managed ingress
- DNS and TLS configured for the public connector URL
- a reachable Meo Mai Moi-compatible main app API
- generated per-environment secrets

## Server Checkout

Clone the repo wherever your deployment automation expects it:

```bash
git clone <repo-url> <deploy-path>
cd <deploy-path>
cp .env.example .env
```

If you run multiple instances on the same server, use separate checkouts and
override `CONNECTOR_PORT` and `REDIS_PORT` in each `.env`.

## Generate Secrets

Run this once per deployment environment. Values must be unique per environment.

```bash
python3 -c "
import secrets
print('OAUTH_CLIENT_SECRET:', secrets.token_urlsafe(32))
print('JWT_SECRET:          ', secrets.token_urlsafe(48))
print('ENCRYPTION_KEY:      ', secrets.token_hex(32))
print('HMAC_SHARED_SECRET:  ', secrets.token_urlsafe(32))
print('CONNECTOR_API_KEY:   ', secrets.token_urlsafe(32))
"
```

Store the output in a secret manager or an uncommitted environment file.

## Connector Configuration

Important `.env` values:

| Variable | Purpose |
|---|---|
| `MAIN_APP_URL` | Public or private URL of the main app instance |
| `CONNECTOR_API_KEY` | Shared secret expected by the main app |
| `OAUTH_CLIENT_ID` | OAuth client id configured in the GPT/action client |
| `OAUTH_CLIENT_SECRET` | OAuth client secret configured in the GPT/action client |
| `JWT_SECRET` | Signs JWTs issued to the GPT/action client |
| `ENCRYPTION_KEY` | 64 hex chars; encrypts the upstream Sanctum token inside JWTs |
| `HMAC_SHARED_SECRET` | Shared HMAC secret expected by the main app |
| `LOG_LEVEL` | `info` for normal deployments, `debug` for troubleshooting |
| `ENVIRONMENT` | Deployment environment label |
| `ADMIN_ENABLED` | Enables the `/admin` dashboard when set to `true` |
| `ADMIN_PASSWORD` | Password for the admin dashboard |
| `RATE_LIMIT_PER_MINUTE` | Per-user connector rate limit |
| `CONNECTOR_PORT` | Host port for the connector HTTP service |
| `REDIS_PORT` | Host port for Redis, if published |

## Main App Configuration

The main app needs matching connector integration values:

```dotenv
GPT_CONNECTOR_API_KEY=<same value as CONNECTOR_API_KEY>
GPT_CONNECTOR_HMAC_SECRET=<same value as HMAC_SHARED_SECRET>
GPT_CONNECTOR_URL=<public HTTPS URL of this connector instance>
```

Restart the main app after changing its runtime configuration.

## Reverse Proxy

Terminate TLS at your reverse proxy and forward traffic to the connector host
port. A minimal nginx location looks like this:

```nginx
location / {
    proxy_pass http://127.0.0.1:<connector-port>;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

Always validate the reverse proxy configuration before reloading it.

## Start

```bash
docker compose up -d --build
docker compose ps
```

Health check:

```bash
curl -fsS <connector-base-url>/health
```

`main_app_reachable: false` means the connector cannot reach `MAIN_APP_URL`.

## CI/CD

The repository includes a Woodpecker pipeline and `utils/deploy-ci.sh` as an
example of SSH-based deployment automation. Configure hostnames, SSH users,
deployment paths, and keys as CI secrets outside the repository.

The expected flow is:

1. CI checks out the pushed commit.
2. CI connects to the target host.
3. The target checkout is moved to the exact commit.
4. `docker compose up -d --build` recreates the connector instance.
5. CI checks the instance-local `/health` endpoint.

Treat pushes to deployment branches as possible live deploy triggers in any
environment that has CI/CD wired up.

## OAuth and Tool Flow Verification

Use the scripts in `scripts/` to verify a live connector against a compatible
main app:

```bash
python scripts/simulate_oauth_flow.py \
  --sanctum-token "<token>" \
  --connector-base "<connector-base-url>" \
  --main-app-base "<main-app-base-url>" \
  --client-id "<oauth-client-id>" \
  --client-secret "<oauth-client-secret>" \
  --redirect-uri "<connector-base-url>/oauth/callback" \
  --verify-tools

JWT_SECRET="<jwt-secret>" \
ENCRYPTION_KEY="<encryption-key>" \
python scripts/simulate_gpt_tool_flow.py \
  --sanctum-token "<token>" \
  --user-id <user-id> \
  --connector-base "<connector-base-url>" \
  --main-app-base "<main-app-base-url>"
```

When validating signup behavior, remember that a newly created user may need to
verify their email before PAT-gated pet routes can succeed. That is an upstream
account-policy state, not necessarily a connector failure.

## Troubleshooting

### `Invalid session signature` on `/api/gpt-auth/confirm`

`HMAC_SHARED_SECRET` in the connector and `GPT_CONNECTOR_HMAC_SECRET` in the
main app do not match.

### `Name or service not known` on callback step

The main app's `GPT_CONNECTOR_URL` is wrong or unset. Set it to the connector's
public HTTPS URL and restart the main app.

### OAuth callback returns `503 GPT connector is not configured.`

The main app is missing connector bridge runtime configuration. Fix the main app
environment, restart it, and retry the OAuth flow.

### Port conflict on startup

Check what is already listening and adjust `CONNECTOR_PORT` or `REDIS_PORT`:

```bash
ss -tlnp | grep -E ':(8001|8002|6379|6380)'
```

### Container exits immediately

```bash
docker compose logs connector
```

The most common cause is a missing or malformed `.env` value.

### Admin dashboard not loading

Set `ADMIN_ENABLED=true` and `ADMIN_PASSWORD=<password>`, then recreate the
connector container.
