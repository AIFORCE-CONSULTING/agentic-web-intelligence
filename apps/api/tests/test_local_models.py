"""Tests for the local-only, no-inference provider boundary."""

import pytest

from app.local_models.service import (
    LocalModelProviderConfigurationError,
    LocalModelProviderService,
)


def test_local_model_endpoint_allows_only_supported_local_addresses() -> None:
    assert (
        LocalModelProviderService.validate_endpoint("http://host.docker.internal:11434/")
        == "http://host.docker.internal:11434"
    )
    assert LocalModelProviderService.validate_endpoint("http://localhost:11434") == "http://localhost:11434"

    with pytest.raises(LocalModelProviderConfigurationError):
        LocalModelProviderService.validate_endpoint("https://ollama.example.com")
    with pytest.raises(LocalModelProviderConfigurationError):
        LocalModelProviderService.validate_endpoint("http://localhost:11434/api/tags")
    with pytest.raises(LocalModelProviderConfigurationError):
        LocalModelProviderService.validate_endpoint("http://user:password@localhost:11434")
