# Deployment Guide

This guide covers deploying the connector on a Linux server with nginx, Docker, and Let's Encrypt SSL.
For local development setup, see [install.md](install.md).

The current production model uses two long-lived checkouts on the `meo` server:

| Branch | Server path | Public URL | Purpose |
|---|---|---|---|
| `main` | `/srv/gpt-connector` | `https://gpt-connector.meo-mai-moi.com` | production |
| `dev` | `/srv/gpt-connector-test` | `https://gpt-connector-test.meo-mai-moi.com` | staging / test |

Those checkouts are now intended to be updated by Woodpecker:

- `push` to `main` deploys `/srv/gpt-connector`
- `push` to `dev` deploys `/srv/gpt-connector-test`
- server-managed files such as `.env`, nginx config, and TLS certificates stay in place and are not overwritten by CI

---

## Architecture overview

```
Internet → nginx (443 SSL) → Docker container (connector:8001) → Redis (6379)
                                        ↓
                           Main app (Meo Mai Moi) API
```

Two independent deployments on the same server share one nginx and one Docker daemon:

| Instance | nginx subdomain                    | Connector port | Redis port |
|----------|------------------------------------|---------------|------------|
| prod     | gpt-connector.meo-mai-moi.com      | 8001          | 6379       |
| test     | gpt-connector-test.meo-mai-moi.com | 8002          | 6380       |

---

## Prerequisites

- Ubuntu/Debian server with:
  - `docker` + `docker compose` plugin
  - `nginx`
  - `certbot` with the nginx plugin (`python3-certbot-nginx`)
  - SSH access as a user with `sudo`
- DNS A records for both subdomains pointing to the server's public IP (must be live before certbot)
- The main app (Meo Mai Moi) running and reachable at its URL

---

## 1. Prepare the server checkouts

```bash
# Production instance
sudo git clone <repo-url> /srv/gpt-connector
sudo chown -R $USER:$USER /srv/gpt-connector

# Test/staging instance (separate clone, independently configurable)
sudo git clone <repo-url> /srv/gpt-connector-test
sudo chown -R $USER:$USER /srv/gpt-connector-test
```

---

## 2. Customize ports (test instance only)

The default `docker-compose.yml` binds the connector to port `8001` and Redis to `6379`.
The test instance must use different ports to avoid conflicts. Edit directly:

```bash
# In /srv/gpt-connector-test/.env
printf '\nCONNECTOR_PORT=8002\nREDIS_PORT=6380\n' >> .env
```

Verify:
```bash
grep -E '^(CONNECTOR_PORT|REDIS_PORT)=' .env
# Expected:
# CONNECTOR_PORT=8002
# REDIS_PORT=6380
```

---

## 3. Generate secrets

Run this once per deployment environment. All values must be unique per environment.

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

Save the output — you will need these values in both the connector `.env` and the main app `.env`.

---

## 4. Configure the connector .env

```bash
cp /srv/gpt-connector-test/.env.example /srv/gpt-connector-test/.env
nano /srv/gpt-connector-test/.env
```

| Variable | Value |
|---|---|
| `MAIN_APP_URL` | URL of the Meo Mai Moi instance this connector targets (e.g. `https://dev.meo-mai-moi.com` for test, `https://meo-mai-moi.com` for prod) |
| `CONNECTOR_API_KEY` | Generated above — must match `GPT_CONNECTOR_API_KEY` in the main app |
| `OAUTH_CLIENT_ID` | `meo-gpt` (fixed — must match what's configured in the ChatGPT Custom GPT) |
| `OAUTH_CLIENT_SECRET` | Generated above — must match what's entered in the ChatGPT Custom GPT OAuth settings |
| `JWT_SECRET` | Generated above — signs JWTs issued to ChatGPT |
| `ENCRYPTION_KEY` | Generated above — 64 hex chars (32 bytes). Encrypts the Sanctum token inside the JWT |
| `HMAC_SHARED_SECRET` | Generated above — must match `GPT_CONNECTOR_HMAC_SECRET` in the main app |
| `REDIS_URL` | Leave unset — docker-compose injects `redis://redis:6379` automatically |
| `LOG_LEVEL` | `info` (use `debug` temporarily when troubleshooting) |
| `ENVIRONMENT` | `production` |
| `ADMIN_ENABLED` | `true` to enable the `/admin` dashboard; `false` to disable |
| `ADMIN_PASSWORD` | Password for the admin dashboard (username is always `admin`) |
| `RATE_LIMIT_PER_MINUTE` | `60` (requests per user per minute) |

Example `.env` for the test instance:

```dotenv
MAIN_APP_URL=https://dev.meo-mai-moi.com
CONNECTOR_API_KEY=LvsIhmJRWk7Mj8G6Qdg4g-KhIGBWOQGuqeG7lgEA2Oo
OAUTH_CLIENT_ID=meo-gpt
OAUTH_CLIENT_SECRET=FznCNM3c-M9snRGL9xASCraN5TEktlaJYk00HxZZTRk
JWT_SECRET=Ap4wEjSC06vSYCIspYZDpXF6HBh0Nl_GsqDKWY6ajp1vSi4DPjdggBtyTWqhPVod
ENCRYPTION_KEY=562d0d7136156f84000fe1c8701ff5950c9c57a8862d6808613b65aa75a1994c
HMAC_SHARED_SECRET=We4ahu6E9hCZBPVodK5N7kPDVq4Uv21-deUNHVz7hi4
LOG_LEVEL=info
ENVIRONMENT=production
ADMIN_ENABLED=true
ADMIN_PASSWORD=<your-admin-password>
RATE_LIMIT_PER_MINUTE=60
```

---

## 5. Configure the main app

The main app needs three environment variables added to its `backend/.env`:

```dotenv
# GPT Connector integration
GPT_CONNECTOR_API_KEY=<same value as CONNECTOR_API_KEY in connector .env>
GPT_CONNECTOR_HMAC_SECRET=<same value as HMAC_SHARED_SECRET in connector .env>
GPT_CONNECTOR_URL=https://gpt-connector-test.meo-mai-moi.com   # or prod subdomain
```

> `GPT_CONNECTOR_URL` is the public HTTPS URL of **this connector instance**. The main app uses it
> to construct the redirect URL returned from `POST /api/gpt-auth/confirm`.

After editing, restart the main app backend container:

```bash
cd ~/meo-mai-moi   # or /srv/meo-mai-moi
docker compose restart backend
```

---

## 6. Configure nginx

Create a config file per subdomain in `/etc/nginx/conf.d/`. Replace the port number to match
the instance (8001 for prod, 8002 for test).

```bash
sudo tee /etc/nginx/conf.d/gpt-connector-test.meo-mai-moi.com.conf > /dev/null << 'EOF'
server {
    server_name gpt-connector-test.meo-mai-moi.com;

    access_log /var/log/nginx/gpt-connector-test.meo-mai-moi.com_access.log;
    error_log  /var/log/nginx/gpt-connector-test.meo-mai-moi.com_error.log error;

    location / {
        proxy_pass http://127.0.0.1:8002;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        proxy_connect_timeout 15s;
        proxy_send_timeout 120s;
        proxy_read_timeout 120s;
    }

    listen 80;
}
EOF
```

Test and reload:

```bash
sudo nginx -t && sudo nginx -s reload
```

---

## 7. Obtain SSL certificates

Use certbot's nginx plugin — it obtains the certificate and updates the nginx configs automatically.
Both subdomains can share a single certificate:

```bash
sudo certbot --nginx \
  -d gpt-connector.meo-mai-moi.com \
  -d gpt-connector-test.meo-mai-moi.com \
  --non-interactive --agree-tos \
  -m admin@catarchy.space
```

Certbot will add `listen 443 ssl` blocks and an HTTP→HTTPS redirect to each config file.
Verify auto-renewal is configured:

```bash
sudo systemctl status certbot.timer
# or
sudo certbot renew --dry-run
```

---

## 8. Start the connector

```bash
cd /srv/gpt-connector-test
docker compose up -d --build
```

Check containers are healthy:

```bash
docker ps --format 'table {{.Names}}\t{{.Ports}}\t{{.Status}}' | grep gpt
```

Expected output:
```
gpt-connector-test-connector-1   0.0.0.0:8002->8000/tcp   Up X minutes (healthy)
gpt-connector-test-redis-1       0.0.0.0:6380->6379/tcp   Up X minutes (healthy)
```

---

## Woodpecker setup

Repo-side CI configuration lives in [`.woodpecker.yml`](../.woodpecker.yml). The deploy helper it calls on the target host is [`utils/deploy-ci.sh`](../utils/deploy-ci.sh).

Required Woodpecker secrets for this repo:

| Secret | Value |
|---|---|
| `MEO_HOST` | `10.23.0.2` |
| `MEO_USER` | `ubuntu` |
| `MEO_SSH_KEY` | private deploy key authorized on `meo` |
| `PROD_DEPLOY_PATH` | `/srv/gpt-connector` |
| `DEV_DEPLOY_PATH` | `/srv/gpt-connector-test` |

Deploy flow:

1. Woodpecker clones the repo for the pushed commit.
2. The matching branch step SSHes to `meo`.
3. The long-lived checkout on `meo` is reset to `CI_COMMIT_SHA`.
4. `docker compose up -d --build` rebuilds just that instance.
5. CI waits for the instance-local `http://127.0.0.1:<port>/health` endpoint to return success.

---

## 9. Verify the deployment

**Health check:**
```bash
curl -s https://gpt-connector-test.meo-mai-moi.com/health | python3 -m json.tool
```

Expected:
```json
{
  "status": "ok",
  "version": "0.2.4",
  "main_app_reachable": true
}
```

`main_app_reachable: false` means the connector cannot reach `MAIN_APP_URL` — check the URL
and that the main app is running.

When validating the signup path in production or staging, remember that a newly created GPT user may still need to verify their email before PAT-gated pet routes such as `GET /pets` or `POST /pets` can succeed. That is an upstream account-policy state, not necessarily a connector failure.

**Full OAuth + tools simulation:**

First, get a Sanctum token from the main app:

```bash
ssh catarchy   # or ssh meo for the prod main app
cd ~/meo-mai-moi
docker compose exec -T backend php artisan tinker --no-interaction <<'EOF'
$user = \App\Models\User::where('email', 'admin@catarchy.space')->first();
echo $user->id . ' ' . $user->createToken('gpt-sim')->plainTextToken;
EOF
```

Note the user ID and the full token string. Then from the connector project root on your local machine:

```bash
# Step 1: Full OAuth flow
python scripts/simulate_oauth_flow.py \
  --sanctum-token "<token>" \
  --connector-base "https://gpt-connector-test.meo-mai-moi.com" \
  --main-app-base "https://dev.meo-mai-moi.com" \
  --client-id "meo-gpt" \
  --client-secret "<OAUTH_CLIENT_SECRET from .env>" \
  --redirect-uri "https://gpt-connector-test.meo-mai-moi.com/oauth/callback" \
  --verify-tools

# Step 2: GPT tool flow (create/find/update pet + health records)
JWT_SECRET="<JWT_SECRET from .env>" \
ENCRYPTION_KEY="<ENCRYPTION_KEY from .env>" \
python scripts/simulate_gpt_tool_flow.py \
  --sanctum-token "<token>" \
  --user-id <user_id> \
  --connector-base "https://gpt-connector-test.meo-mai-moi.com" \
  --main-app-base "https://dev.meo-mai-moi.com"
```

All steps in both scripts should return 2xx status codes.

For Custom GPT behavior, keep the onboarding wording aligned with the current account flow:
- if the user already has a Meo Mai Moi account, the GPT should tell them to use Connect Account and sign in on the Meo Mai Moi page
- if the user needs a new account, the GPT should ask which email they want to use before sending them into Connect Account
- the GPT should not ask for passwords in chat
- if email verification is enabled upstream, the GPT should warn that protected pet tools may require email verification before they work

---

## 10. Upgrading

```bash
cd /srv/gpt-connetcor-test
git pull
docker compose up -d --build
```

The build is fast (dependencies are cached in the Docker layer). Redis data and container state
are preserved across rebuilds since `--build` only recreates the connector container.

---

## Troubleshooting

### `Invalid session signature` on `/api/gpt-auth/confirm`

`HMAC_SHARED_SECRET` (connector) and `GPT_CONNECTOR_HMAC_SECRET` (main app) do not match.
Copy the value from the connector `.env` to the main app `.env` and restart the main app backend.

### `Name or service not known` on callback step

The main app's `GPT_CONNECTOR_URL` is wrong or unset (defaults to an old placeholder value).
Set it to the connector's public HTTPS URL and restart the main app backend.

### `KeyError: 'sanctum_token'` in connector logs

The connector is trying to access the exchange response without unwrapping the main app's
`{"success": true, "data": {...}}` envelope. This is fixed in `src/services/main_app.py` —
check that you are running the latest code.

### `422 country field is required` on `POST /pets`

The `country` field (2-letter ISO code) is required by the main app but wasn't included in the
GPT request. The GPT should ask the user for their country if not clear from context. This was
a known gap in earlier versions — `country` is now included in the `CreatePetRequest` schema.

### Upstream `429` now reaches the GPT as `429`

This is expected after the connector update. The connector now preserves upstream rate-limit and quota meaning instead of rewriting `429` into a generic `502`.

If the main app includes safe quota metadata, the connector keeps it in the error payload so support and debugging can distinguish minute throttling from daily quota exhaustion.

### Port conflict on startup

Check what is already listening before starting a new instance:
```bash
ss -tlnp | grep -E ':(8001|8002|6379|6380)'
```

The prod connector uses 8001/6379, test uses 8002/6380. Make sure the `docker-compose.yml`
in the test directory has been patched (step 2 above).

### Container exits immediately

Check logs:
```bash
docker compose logs connector
```

Most common cause: a required `.env` variable is missing or malformed (e.g. `ENCRYPTION_KEY`
not exactly 64 hex characters).

### Admin dashboard not loading

Set `ADMIN_ENABLED=true` and `ADMIN_PASSWORD=<something>` in `.env`, then rebuild:
```bash
docker compose up -d --build connector
```

Access at `https://<subdomain>/admin` with username `admin`.
