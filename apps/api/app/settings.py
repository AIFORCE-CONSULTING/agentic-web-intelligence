"""Application configuration loaded from environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings for the platform API."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_environment: str = "development"
    app_log_level: str = "INFO"
    web_origin: str = "http://localhost:5173"
    searxng_base_url: str | None = None


@lru_cache
def get_settings() -> Settings:
    """Return cached, validated runtime settings."""

    return Settings()
