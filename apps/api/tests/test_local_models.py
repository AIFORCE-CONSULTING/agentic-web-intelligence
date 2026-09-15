"""Tests for the local-only, no-inference provider boundary."""

import pytest

from app.local_models.service import (
    LocalModelProviderConfigurationError,
    LocalModelProviderService,
)
from evidence_intelligence.consolidation import (
    MAX_CONSOLIDATION_INPUT_CHARACTERS,
    group_within_budget,
)


def test_consolidation_groups_are_deterministic_and_bounded() -> None:
    items = ["a" * 5_999, "b" * 5_999, "c" * 5_999]

    groups = group_within_budget(items, lambda item: item)

    assert groups == ((items[0], items[1]), (items[2],))
    assert all(
        sum(len(item) + 2 for item in group) <= MAX_CONSOLIDATION_INPUT_CHARACTERS
        for group in groups
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
