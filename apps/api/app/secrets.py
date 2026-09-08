"""Allowlisted deployment secrets with safe status and recursive redaction."""

from dataclasses import dataclass
from enum import StrEnum

from pydantic import BaseModel

from app.settings import Settings


class SecretName(StrEnum):
    """Secrets the platform is permitted to resolve from its deployment provider."""

    AUTH_BOOTSTRAP = "auth.bootstrap"
    OIDC_CLIENT_SECRET = "identity.oidc.client_secret"
    GITHUB_CONNECTOR_TOKEN = "connector.github.token"


@dataclass(frozen=True)
class SecretDefinition:
    name: SecretName
    environment_variable: str
    purpose: str


SECRET_DEFINITIONS: tuple[SecretDefinition, ...] = (
    SecretDefinition(
        SecretName.AUTH_BOOTSTRAP,
        "AUTH_BOOTSTRAP_SECRET",
        "One-time local administrator initialization.",
    ),
    SecretDefinition(
        SecretName.OIDC_CLIENT_SECRET,
        "OIDC_CLIENT_SECRET",
        "Future confidential-client OIDC code exchange.",
    ),
    SecretDefinition(
        SecretName.GITHUB_CONNECTOR_TOKEN,
        "GITHUB_CONNECTOR_TOKEN",
        "Future governed GitHub connector calls.",
    ),
)


class SecretStatus(BaseModel):
    """Safe operator-facing status that never includes a secret value."""

    name: SecretName
    configured: bool
    valid: bool
    purpose: str
    detail: str


class SecretStatusList(BaseModel):
    """Credential-free inventory of the platform's fixed secret registry."""

    secrets: list[SecretStatus]


class DeploymentSecrets:
    """Environment-backed local provider, replaceable by a managed vault adapter later."""

    def __init__(self, settings: Settings) -> None:
        self._values: dict[SecretName, str | None] = {
            SecretName.AUTH_BOOTSTRAP: settings.auth_bootstrap_secret,
            SecretName.OIDC_CLIENT_SECRET: settings.oidc_client_secret,
            SecretName.GITHUB_CONNECTOR_TOKEN: settings.github_connector_token,
        }

    def get(self, name: SecretName) -> str | None:
        """Return a value only to trusted server-side code."""

        value = self._values[name]
        return value if value and value.strip() else None

    def status(self) -> SecretStatusList:
        return SecretStatusList(
            secrets=[
                SecretStatus(
                    name=definition.name,
                    configured=self.get(definition.name) is not None,
                    valid=self._validation_error(definition.name) is None,
                    purpose=definition.purpose,
                    detail=self._status_detail(definition.name),
                )
                for definition in SECRET_DEFINITIONS
            ]
        )

    def redact(self, value: object) -> object:
        """Remove all configured secret values from data intended for logs or persistence."""

        secret_values = sorted(
            (secret for secret in self._values.values() if secret and secret.strip()),
            key=len,
            reverse=True,
        )
        return _redact_value(value, secret_values)

    def _validation_error(self, name: SecretName) -> str | None:
        value = self.get(name)
        if value is None:
            return None
        if name is SecretName.AUTH_BOOTSTRAP and len(value) < 32:
            return "must be at least 32 characters"
        return None

    def _status_detail(self, name: SecretName) -> str:
        if self.get(name) is None:
            return "Not configured."
        error = self._validation_error(name)
        return f"Configured but {error}." if error else "Configured and valid."


def _redact_value(value: object, secrets: list[str]) -> object:
    if isinstance(value, str):
        redacted = value
        for secret in secrets:
            redacted = redacted.replace(secret, "[REDACTED]")
        return redacted
    if isinstance(value, dict):
        return {str(key): _redact_value(item, secrets) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact_value(item, secrets) for item in value]
    if isinstance(value, tuple):
        return tuple(_redact_value(item, secrets) for item in value)
    return value
