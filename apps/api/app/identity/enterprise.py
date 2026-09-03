"""Provider-neutral, server-only configuration boundary for enterprise identity."""

from dataclasses import dataclass
from urllib.parse import urlparse

from app.identity.contracts import EnterpriseIdentityStatus
from app.settings import Settings


class EnterpriseIdentityConfigurationError(ValueError):
    """Raised when a deployment has supplied an unsafe or partial OIDC configuration."""


@dataclass(frozen=True)
class EnterpriseIdentityConfiguration:
    """Validated values required by a future confidential-client OIDC adapter.

    This boundary deliberately does not perform discovery, redirect a browser, or
    exchange a code. Those actions belong to the later, token-validating adapter.
    """

    provider_name: str
    issuer_url: str
    client_id: str
    client_secret: str
    redirect_uri: str


def _require_safe_url(value: str, field_name: str, *, issuer: bool = False) -> str:
    parsed = urlparse(value)
    is_localhost = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise EnterpriseIdentityConfigurationError(f"{field_name} must be an absolute URL.")
    if parsed.scheme != "https" and not is_localhost:
        raise EnterpriseIdentityConfigurationError(
            f"{field_name} must use HTTPS outside local development."
        )
    if issuer and (parsed.query or parsed.fragment):
        raise EnterpriseIdentityConfigurationError(
            "OIDC_ISSUER_URL must not contain a query string or fragment."
        )
    return value.rstrip("/") if issuer else value


def _require_non_blank(value: str, field_name: str) -> str:
    if not value.strip():
        raise EnterpriseIdentityConfigurationError(f"{field_name} must not be blank.")
    return value


class EnterpriseIdentityBoundary:
    """Expose configuration readiness without exposing credentials or contacting a provider."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def configuration(self) -> EnterpriseIdentityConfiguration | None:
        """Return validated OIDC configuration, or None when enterprise SSO is disabled."""

        values = {
            "OIDC_ISSUER_URL": self._settings.oidc_issuer_url,
            "OIDC_CLIENT_ID": self._settings.oidc_client_id,
            "OIDC_CLIENT_SECRET": self._settings.oidc_client_secret,
            "OIDC_REDIRECT_URI": self._settings.oidc_redirect_uri,
        }
        supplied = {name: value for name, value in values.items() if value}
        if not supplied:
            return None
        missing = [name for name, value in values.items() if not value]
        if missing:
            raise EnterpriseIdentityConfigurationError(
                "Enterprise OIDC configuration is incomplete; missing " + ", ".join(missing) + "."
            )

        return EnterpriseIdentityConfiguration(
            provider_name=self._settings.oidc_provider_name or "OpenID Connect",
            issuer_url=_require_safe_url(
                self._settings.oidc_issuer_url or "", "OIDC_ISSUER_URL", issuer=True
            ),
            client_id=_require_non_blank(self._settings.oidc_client_id or "", "OIDC_CLIENT_ID"),
            client_secret=_require_non_blank(
                self._settings.oidc_client_secret or "", "OIDC_CLIENT_SECRET"
            ),
            redirect_uri=_require_safe_url(
                self._settings.oidc_redirect_uri or "", "OIDC_REDIRECT_URI"
            ),
        )

    def status(self) -> EnterpriseIdentityStatus:
        """Provide deployment-safe readiness information for operators and the console."""

        try:
            configuration = self.configuration()
        except EnterpriseIdentityConfigurationError as error:
            return EnterpriseIdentityStatus(
                mode="invalid",
                provider_name=self._settings.oidc_provider_name,
                issuer_url=None,
                detail=str(error),
            )
        if configuration is None:
            return EnterpriseIdentityStatus(
                mode="disabled",
                provider_name=None,
                issuer_url=None,
                detail="Enterprise SSO is not configured; local sign-in remains available.",
            )
        return EnterpriseIdentityStatus(
            mode="ready",
            provider_name=configuration.provider_name,
            issuer_url=configuration.issuer_url,
            detail=(
                "Configuration is ready for a future server-side OIDC adapter. "
                "No provider redirect or token exchange is enabled yet."
            ),
        )
