from __future__ import annotations

import uuid
from typing import Any

import httpx

from src.core.config import Settings


class MainAppError(Exception):
    def __init__(self, status_code: int, payload: dict[str, Any]):
        self.status_code = status_code
        self.payload = payload
        super().__init__(payload.get("message", "Main app error"))


_PET_TYPES_BY_NAME: dict[str, int] = {}
_PET_TYPES_BY_ID: dict[int, str] = {}


def _request_id() -> str:
    return f"req_{uuid.uuid4().hex[:12]}"


def _extract_fields(upstream_data: Any) -> list[dict[str, str]]:
    if not isinstance(upstream_data, dict):
        return []
    errors = upstream_data.get("errors")
    if not isinstance(errors, dict):
        return []

    normalized: list[dict[str, str]] = []
    for name, reasons in errors.items():
        if isinstance(reasons, list) and reasons:
            normalized.append({"name": str(name), "reason": str(reasons[0])})
        else:
            normalized.append({"name": str(name), "reason": "invalid"})
    return normalized


def _message_from_upstream(upstream_data: Any, fallback: str) -> str:
    if isinstance(upstream_data, dict):
        message = upstream_data.get("message")
        if isinstance(message, str) and message.strip():
            return message
    return fallback


def _normalize_http_error(status_code: int, upstream_data: Any) -> tuple[int, dict[str, Any]]:
    request_id = _request_id()

    if status_code == 401:
        return 401, {
            "error": "UNAUTHORIZED",
            "message": _message_from_upstream(upstream_data, "Authentication failed."),
            "fields": [],
            "request_id": request_id,
        }
    if status_code == 404:
        return 404, {
            "error": "NOT_FOUND",
            "message": _message_from_upstream(upstream_data, "Requested resource was not found."),
            "fields": [],
            "request_id": request_id,
        }
    if status_code == 422:
        return 422, {
            "error": "VALIDATION_ERROR",
            "message": _message_from_upstream(upstream_data, "Validation failed."),
            "fields": _extract_fields(upstream_data),
            "request_id": request_id,
        }
    if status_code == 429:
        return 502, {
            "error": "UPSTREAM_ERROR",
            "message": "The server is busy, please try again in a moment.",
            "fields": [],
            "request_id": request_id,
        }
    if status_code >= 500:
        return 502, {
            "error": "UPSTREAM_ERROR",
            "message": "Main app is temporarily unavailable.",
            "fields": [],
            "request_id": request_id,
        }

    return 502, {
        "error": "UPSTREAM_ERROR",
        "message": _message_from_upstream(upstream_data, "Unexpected upstream error."),
        "fields": [],
        "request_id": request_id,
    }


async def call_main_app(
    *,
    method: str,
    path: str,
    settings: Settings,
    sanctum_token: str | None = None,
    use_connector_api_key: bool = False,
    json_data: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
    timeout: float = 10.0,
    return_status: bool = False,
) -> Any:
    headers: dict[str, str] = {}
    if sanctum_token:
        headers["Authorization"] = f"Bearer {sanctum_token}"
    elif use_connector_api_key:
        headers["Authorization"] = f"Bearer {settings.CONNECTOR_API_KEY}"

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.request(
                method=method,
                url=f"{settings.MAIN_APP_URL}{path}",
                headers=headers,
                json=json_data,
                params=params,
            )
    except httpx.RequestError as exc:
        raise MainAppError(
            status_code=502,
            payload={
                "error": "UPSTREAM_ERROR",
                "message": "Main app is unreachable.",
                "fields": [],
                "request_id": _request_id(),
            },
        ) from exc

    if 200 <= resp.status_code < 300:
        if not resp.content:
            payload: Any = {}
            return (resp.status_code, payload) if return_status else payload
        try:
            payload = resp.json()
        except ValueError:
            payload = {}
        return (resp.status_code, payload) if return_status else payload

    try:
        upstream_data = resp.json()
    except ValueError:
        upstream_data = {"message": resp.text}

    normalized_status, payload = _normalize_http_error(resp.status_code, upstream_data)
    raise MainAppError(status_code=normalized_status, payload=payload)


async def refresh_pet_types_cache(settings: Settings) -> None:
    data = await call_main_app(
        method="GET",
        path="/api/pet-types",
        settings=settings,
        timeout=8.0,
    )

    items = data if isinstance(data, list) else data.get("data", [])
    by_name: dict[str, int] = {}
    by_id: dict[int, str] = {}

    if isinstance(items, list):
        for item in items:
            if not isinstance(item, dict):
                continue
            raw_id = item.get("id")
            raw_name = item.get("name")
            if not isinstance(raw_name, str):
                continue
            try:
                pet_type_id = int(raw_id)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                continue
            normalized_name = raw_name.strip().lower()
            if not normalized_name:
                continue
            by_name[normalized_name] = pet_type_id
            by_id[pet_type_id] = normalized_name

    _PET_TYPES_BY_NAME.clear()
    _PET_TYPES_BY_NAME.update(by_name)
    _PET_TYPES_BY_ID.clear()
    _PET_TYPES_BY_ID.update(by_id)


def get_pet_types_by_name() -> dict[str, int]:
    return dict(_PET_TYPES_BY_NAME)


def get_species_name_by_pet_type_id() -> dict[int, str]:
    return dict(_PET_TYPES_BY_ID)


async def exchange_code(code: str, settings: Settings) -> dict[str, Any]:
    """Exchange a one-time auth code for a Sanctum token + user_id from the main app."""
    data = await call_main_app(
        method="POST",
        path="/api/gpt-auth/exchange",
        settings=settings,
        use_connector_api_key=True,
        json_data={"code": code},
    )
    if not isinstance(data, dict):
        raise MainAppError(
            status_code=502,
            payload={
                "error": "UPSTREAM_ERROR",
                "message": "Invalid response from main app.",
                "fields": [],
                "request_id": _request_id(),
            },
        )
    return data.get("data", data) if "data" in data else data


async def revoke_token(sanctum_token: str, settings: Settings) -> None:
    """Notify the main app to revoke a Sanctum token (best-effort)."""
    await call_main_app(
        method="POST",
        path="/api/gpt-auth/revoke",
        settings=settings,
        use_connector_api_key=True,
        json_data={"token": sanctum_token},
    )
