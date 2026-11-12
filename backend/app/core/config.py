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


@lru_cache
def get_settings() -> Settings:
    return Settings()
