"""Tests for the initial agentic research capability catalog."""

import pytest

from app.agentic_research.capabilities import (
    RESEARCH_CAPABILITY_CATALOG_VERSION,
    AgentResearchCapabilityCatalog,
    ResearchCapabilityError,
)
from app.web_research.mcp_host import GovernedWebToolPolicy


def test_catalog_is_derived_from_the_governed_mcp_registry() -> None:
    policy = GovernedWebToolPolicy()
    catalog = AgentResearchCapabilityCatalog(policy).catalog(["web.search", "web.extract"])
    registry = {tool.name: tool for tool in policy.registry().tools}

    assert catalog.version == RESEARCH_CAPABILITY_CATALOG_VERSION
    assert [tool.name for tool in catalog.capabilities] == ["web.search", "web.extract"]
    for capability in catalog.capabilities:
        assert capability.description == registry[capability.name].purpose
        assert capability.input_schema == registry[capability.name].input_schema
        assert capability.output_contract == registry[capability.name].output_contract


def test_catalog_shows_only_capabilities_granted_to_the_current_step() -> None:
    catalog = AgentResearchCapabilityCatalog().catalog(["web.search"])

    assert [tool.name for tool in catalog.capabilities] == ["web.search"]
    assert "cookie" not in str(catalog.model_dump()).lower()


def test_step_without_initial_research_grants_receives_no_catalog() -> None:
    with pytest.raises(ResearchCapabilityError, match="no granted"):
        AgentResearchCapabilityCatalog().catalog([])


@pytest.mark.parametrize("capability", ["web.resolve_public_consent", "browser.click", "shell"])
def test_unknown_or_deferred_capabilities_are_rejected(capability: str) -> None:
    with pytest.raises(ResearchCapabilityError, match="not in"):
        AgentResearchCapabilityCatalog().validate_request(
            capability,
            {},
            ["web.search", "web.extract"],
        )


def test_ungranted_initial_capability_is_rejected() -> None:
    with pytest.raises(ResearchCapabilityError, match="not granted"):
        AgentResearchCapabilityCatalog().validate_request(
            "web.extract",
            {"url": "https://example.com/evidence"},
            ["web.search"],
            ["https://example.com/evidence"],
        )


def test_bounded_search_request_is_normalized() -> None:
    request = AgentResearchCapabilityCatalog().validate_request(
        "web.search",
        {"query": "agentic web identity", "max_results": 10},
        ["web.search"],
    )

    assert request.catalog_version == RESEARCH_CAPABILITY_CATALOG_VERSION
    assert request.capability == "web.search"
    assert request.arguments == {"query": "agentic web identity", "max_results": 10}


@pytest.mark.parametrize(
    "arguments",
    [
        {"query": "agentic web", "max_results": 51},
        {"query": "agentic web", "max_results": 5, "crawl": True},
        {"query": "x" * 513, "max_results": 5},
    ],
)
def test_invalid_or_extra_search_arguments_are_rejected(arguments: dict[str, object]) -> None:
    with pytest.raises(ResearchCapabilityError, match="invalid arguments"):
        AgentResearchCapabilityCatalog().validate_request(
            "web.search",
            arguments,
            ["web.search"],
        )


def test_evidence_acquisition_requires_a_discovered_source() -> None:
    catalog = AgentResearchCapabilityCatalog()
    url = "https://example.com/evidence"

    request = catalog.validate_request(
        "web.extract",
        {"url": url},
        ["web.extract"],
        [url],
    )

    assert request.arguments == {"url": url}
    with pytest.raises(ResearchCapabilityError, match="only from a source discovered"):
        catalog.validate_request(
            "web.extract",
            {"url": "https://unrelated.example/evidence"},
            ["web.extract"],
            [url],
        )


def test_evidence_acquisition_rejects_extra_browser_controls() -> None:
    url = "https://example.com/evidence"

    with pytest.raises(ResearchCapabilityError, match="invalid arguments"):
        AgentResearchCapabilityCatalog().validate_request(
            "web.extract",
            {"url": url, "click": "Accept all cookies"},
            ["web.extract"],
            [url],
        )
