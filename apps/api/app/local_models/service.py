"""Narrow, local-only Ollama readiness boundary; never performs inference."""

from urllib.parse import urlparse
from uuid import UUID

import httpx

from app.local_models.contracts import LocalModelProviderConfiguration, LocalModelProviderReadiness
from app.local_models.store import LocalModelProviderStore

_LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1", "host.docker.internal"})


class LocalModelProviderConfigurationError(ValueError):
    """Raised for a configuration outside the local provider boundary."""


class LocalModelProviderService:
    def __init__(self, store: LocalModelProviderStore) -> None:
        self._store = store

    @staticmethod
    def validate_endpoint(endpoint_url: str) -> str:
        parsed = urlparse(endpoint_url.strip())
        if parsed.scheme != "http" or parsed.hostname not in _LOCAL_HOSTS or parsed.query or parsed.fragment:
            raise LocalModelProviderConfigurationError(
                "Ollama endpoint must be an HTTP local address (localhost, 127.0.0.1, or host.docker.internal)."
            )
        if parsed.path not in {"", "/"} or parsed.username or parsed.password:
            raise LocalModelProviderConfigurationError("Ollama endpoint must not include credentials or a path.")
        return endpoint_url.strip().rstrip("/")

    async def configuration(self, workspace_id: UUID) -> LocalModelProviderConfiguration | None:
        return await self._store.get(workspace_id)

    async def save(self, workspace_id: UUID, endpoint_url: str, model_name: str) -> LocalModelProviderConfiguration:
        return await self._store.save(workspace_id, self.validate_endpoint(endpoint_url), model_name.strip())

    async def readiness(self, workspace_id: UUID) -> LocalModelProviderReadiness:
        configuration = await self.configuration(workspace_id)
        if configuration is None:
            return LocalModelProviderReadiness(mode="unconfigured", detail="Local Ollama is not configured for this workspace.")
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                response = await client.get(f"{configuration.endpoint_url}/api/tags")
            response.raise_for_status()
            models = response.json().get("models", [])
            available = {item.get("name") for item in models if isinstance(item, dict)}
        except (httpx.HTTPError, ValueError, TypeError):
            return LocalModelProviderReadiness(
                mode="unavailable", endpoint_url=configuration.endpoint_url,
                model_name=configuration.model_name, detail="Local Ollama is unavailable or returned an invalid readiness response."
            )
        if configuration.model_name not in available:
            return LocalModelProviderReadiness(
                mode="invalid", endpoint_url=configuration.endpoint_url,
                model_name=configuration.model_name, detail="Ollama is reachable, but the configured model is not installed."
            )
        return LocalModelProviderReadiness(
            mode="ready", endpoint_url=configuration.endpoint_url,
            model_name=configuration.model_name, detail="Local Ollama is ready; no inference has been performed."
        )
