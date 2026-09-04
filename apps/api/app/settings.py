"""Application configuration loaded from environment variables."""

from functools import lru_cache
from urllib.parse import urlparse

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings for the platform API."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_environment: str = "development"
    app_log_level: str = "INFO"
    web_origin: str = "http://localhost:5173"
    searxng_base_url: str | None = None
    database_url: str | None = None
    auth_bootstrap_secret: str | None = None
    oidc_provider_name: str | None = None
    oidc_issuer_url: str | None = None
    oidc_client_id: str | None = None
    oidc_client_secret: str | None = None
    oidc_redirect_uri: str | None = None
    github_connector_token: str | None = None
    github_project_owner: str | None = None
    # Kept as text so Docker Compose's empty-string default means "not configured".
    github_project_number: str | None = None

    def validate_runtime_configuration(self) -> None:
        """Reject deployment combinations that would weaken browser or identity security."""

        if self.app_environment not in {"development", "test", "production"}:
            raise ValueError("APP_ENVIRONMENT must be development, test, or production.")
        if self.auth_bootstrap_secret and len(self.auth_bootstrap_secret) < 32:
            raise ValueError("AUTH_BOOTSTRAP_SECRET must be at least 32 characters.")
        if self.app_environment == "production":
            parsed_origin = urlparse(self.web_origin)
            if parsed_origin.scheme != "https" or not parsed_origin.netloc:
                raise ValueError("WEB_ORIGIN must use HTTPS in production.")
        oidc_values = (
            self.oidc_issuer_url,
            self.oidc_client_id,
            self.oidc_client_secret,
            self.oidc_redirect_uri,
        )
        if any(oidc_values) and not all(oidc_values):
            raise ValueError(
                "OIDC configuration must provide issuer, client ID, secret, and redirect URI."
            )


@lru_cache
def get_settings() -> Settings:
    """Return cached, validated runtime settings."""

    return Settings()
