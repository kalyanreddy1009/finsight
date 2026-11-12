"""Application settings, read from FINSIGHT_* environment variables."""

from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FINSIGHT_", extra="ignore")

    db_path: str = "finsight.db"
    db_driver: Literal["sqlite", "sqlcipher"] = "sqlite"
    db_key: SecretStr | None = None
    cloud_ai_enabled: bool = False
    # Signs access tokens; must be at least 32 bytes. Required to start the API.
    jwt_secret: SecretStr | None = None
    # One-time secret that must accompany POST /auth/setup (first-run owner creation).
    setup_token: SecretStr | None = None
    # Hex-encoded 32-byte key for AES-256-GCM (PDF password rules, stored statement files).
    master_key: SecretStr | None = None
    docs_dir: str = "docs_store"
    # Browser origins allowed to call the API (e.g. the Vite dev server). Empty = same-origin only.
    allowed_origins: list[str] = []


@lru_cache
def get_settings() -> Settings:
    return Settings()
