import httpx

from src.core.config import Settings


async def exchange_code(code: str, settings: Settings) -> dict:
    """Exchange a one-time auth code for a Sanctum token + user_id from the main app."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{settings.MAIN_APP_URL}/api/gpt-auth/exchange",
            json={"code": code},
            headers={"Authorization": f"Bearer {settings.CONNECTOR_API_KEY}"},
        )
        resp.raise_for_status()
        return resp.json()


async def revoke_token(sanctum_token: str, settings: Settings) -> None:
    """Notify the main app to revoke a Sanctum token (best-effort)."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{settings.MAIN_APP_URL}/api/gpt-auth/revoke",
            json={"token": sanctum_token},
            headers={"Authorization": f"Bearer {settings.CONNECTOR_API_KEY}"},
        )
        resp.raise_for_status()
