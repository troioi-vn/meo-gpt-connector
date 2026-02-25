from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )

    MAIN_APP_URL: str
    CONNECTOR_PUBLIC_URL: str = "http://localhost:8000"
    CONNECTOR_API_KEY: str
    OAUTH_CLIENT_ID: str = "meo-gpt"
    OAUTH_CLIENT_SECRET: str
    JWT_SECRET: str
    ENCRYPTION_KEY: str  # 32-byte hex for AES-256-GCM
    HMAC_SHARED_SECRET: str
    REDIS_URL: str = "redis://localhost:6379"
    LOG_LEVEL: str = "info"
    ENVIRONMENT: str = "production"
    ADMIN_ENABLED: bool = False
    ADMIN_PASSWORD: str = ""
    RATE_LIMIT_PER_MINUTE: int = 60

    @field_validator("MAIN_APP_URL")
    @classmethod
    def strip_trailing_slash(cls, v: str) -> str:
        return v.rstrip("/")

    @field_validator("CONNECTOR_PUBLIC_URL")
    @classmethod
    def validate_connector_public_url(cls, v: str) -> str:
        value = v.rstrip("/")
        if not (value.startswith("http://") or value.startswith("https://")):
            raise ValueError("CONNECTOR_PUBLIC_URL must start with http:// or https://")
        return value

    @field_validator("ENCRYPTION_KEY")
    @classmethod
    def validate_encryption_key(cls, v: str) -> str:
        try:
            key_bytes = bytes.fromhex(v)
        except ValueError as exc:
            raise ValueError("ENCRYPTION_KEY must be a valid hex string") from exc
        if len(key_bytes) != 32:
            raise ValueError("ENCRYPTION_KEY must decode to exactly 32 bytes (64 hex chars)")
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
