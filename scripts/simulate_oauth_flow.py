#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse, urlunparse

import httpx


def _load_dotenv() -> None:
    env_file = Path(".env")
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def _host_friendly_main_app_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.hostname == "host.docker.internal":
        return urlunparse((parsed.scheme or "http", f"localhost:{parsed.port or 8000}", "", "", "", ""))
    return url


def main() -> int:
    _load_dotenv()

    parser = argparse.ArgumentParser(description="Simulate full connector OAuth flow end-to-end.")
    parser.add_argument("--sanctum-token", required=True, help="Main app Sanctum token used for /api/gpt-auth/confirm.")
    parser.add_argument("--connector-base", default="http://localhost:8001", help="Connector base URL.")
    parser.add_argument("--main-app-base", default=None, help="Main app base URL. Defaults to MAIN_APP_URL from .env, with host-friendly normalization.")
    parser.add_argument("--client-id", default=os.environ.get("OAUTH_CLIENT_ID", "meo-gpt"), help="OAuth client ID expected by connector.")
    parser.add_argument("--client-secret", default=os.environ.get("OAUTH_CLIENT_SECRET"), help="OAuth client secret expected by connector.")
    parser.add_argument("--redirect-uri", default="http://localhost:9999/callback", help="Redirect URI to use in authorize request.")
    parser.add_argument("--state", default=None, help="Optional fixed OAuth state.")
    parser.add_argument("--verify-tools", action="store_true", help="After token exchange, call GET /pets to verify token usability.")
    args = parser.parse_args()

    if not args.client_secret:
        raise SystemExit("Missing --client-secret (or OAUTH_CLIENT_SECRET in .env)")

    connector_base = args.connector_base.rstrip("/")
    main_app_base_raw = args.main_app_base or os.environ.get("MAIN_APP_URL", "http://localhost:8000")
    main_app_base = _host_friendly_main_app_url(main_app_base_raw.rstrip("/"))
    state = args.state or f"sim-{int(time.time())}"

    summary: dict[str, Any] = {
        "connector_base": connector_base,
        "main_app_base": main_app_base,
        "state": state,
        "steps": [],
    }

    with httpx.Client(timeout=20.0, follow_redirects=False) as client:
        authorize = client.get(
            f"{connector_base}/oauth/authorize",
            params={
                "client_id": args.client_id,
                "response_type": "code",
                "redirect_uri": args.redirect_uri,
                "state": state,
            },
        )
        authorize_loc = authorize.headers.get("location", "")
        summary["steps"].append({
            "step": "authorize",
            "status": authorize.status_code,
            "location": authorize_loc,
        })

        if authorize.status_code != 302:
            print(json.dumps(summary, indent=2, ensure_ascii=False))
            return 1

        parsed = urlparse(authorize_loc)
        query = parse_qs(parsed.query)
        session_id = query.get("session_id", [None])[0]
        session_sig = query.get("session_sig", [None])[0]
        if session_id is None or session_sig is None:
            print(json.dumps(summary, indent=2, ensure_ascii=False))
            return 1

        confirm = client.post(
            f"{main_app_base}/api/gpt-auth/confirm",
            headers={
                "Authorization": f"Bearer {args.sanctum_token}",
                "Accept": "application/json",
            },
            json={"session_id": session_id, "session_sig": session_sig},
        )
        confirm_body = confirm.json() if confirm.content else {}
        summary["steps"].append({
            "step": "confirm",
            "status": confirm.status_code,
            "body": confirm_body,
        })

        if confirm.status_code >= 400 or not isinstance(confirm_body, dict) or "data" not in confirm_body:
            print(json.dumps(summary, indent=2, ensure_ascii=False))
            return 1

        redirect_url = confirm_body["data"].get("redirect_url")
        if not isinstance(redirect_url, str):
            print(json.dumps(summary, indent=2, ensure_ascii=False))
            return 1

        callback = client.get(redirect_url)
        token_redirect = callback.headers.get("location", "")
        summary["steps"].append({
            "step": "callback",
            "status": callback.status_code,
            "location": token_redirect,
        })

        if callback.status_code != 302:
            print(json.dumps(summary, indent=2, ensure_ascii=False))
            return 1

        callback_query = parse_qs(urlparse(token_redirect).query)
        connector_code = callback_query.get("code", [None])[0]
        if connector_code is None:
            print(json.dumps(summary, indent=2, ensure_ascii=False))
            return 1

        token = client.post(
            f"{connector_base}/oauth/token",
            data={
                "client_id": args.client_id,
                "client_secret": args.client_secret,
                "grant_type": "authorization_code",
                "code": connector_code,
            },
        )
        token_body = token.json() if token.content else {}
        access_token = token_body.get("access_token") if isinstance(token_body, dict) else None
        summary["steps"].append({
            "step": "token",
            "status": token.status_code,
            "has_access_token": isinstance(access_token, str),
        })

        if token.status_code >= 400 or not isinstance(access_token, str):
            print(json.dumps(summary, indent=2, ensure_ascii=False))
            return 1

        if args.verify_tools:
            verify = client.get(
                f"{connector_base}/pets",
                headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
            )
            summary["steps"].append({
                "step": "verify_get_pets",
                "status": verify.status_code,
            })

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
