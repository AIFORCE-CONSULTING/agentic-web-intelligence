"""Tests for the initial agentic research capability catalog."""

import asyncio
from uuid import uuid4

import pytest

from app.agent_runtime.contracts import McpExecutionCorrelation
from app.agent_runtime.service import RuntimePlanError
from app.agentic_research.capabilities import (
    RESEARCH_CAPABILITY_CATALOG_VERSION,
    AgentResearchCapabilityCatalog,
)
from app.web_research.contracts import SearchResponse
from app.web_research.mcp_host import GovernedWebMcpHost, GovernedWebToolPolicy


def test_catalog_is_derived_from_the_governed_mcp_registry() -> None:
    policy = GovernedWebToolPolicy()
    catalog = AgentResearchCapabilityCatalog(policy).catalog()
    registry = {tool.name: tool for tool in policy.registry().tools}

    assert catalog.version == RESEARCH_CAPABILITY_CATALOG_VERSION
    assert [tool.name for tool in catalog.capabilities] == ["web.search", "web.extract"]
    for capability in catalog.capabilities:
        assert capability.description == registry[capability.name].purpose
        assert capability.input_schema == registry[capability.name].input_schema
        assert capability.output_contract == registry[capability.name].output_contract


def test_catalog_exposes_schemas_without_claiming_execution_authority() -> None:
    catalog = AgentResearchCapabilityCatalog().catalog()

    assert set(catalog.model_dump()) == {"version", "capabilities"}
    assert "grant" not in str(catalog.model_dump()).lower()
    assert "cookie" not in str(catalog.model_dump()).lower()


def execution_correlation() -> McpExecutionCorrelation:
    return McpExecutionCorrelation(
        workspace_id=uuid4(),
        research_run_id=uuid4(),
        runtime_run_id=uuid4(),
        runtime_step_id=uuid4(),
        authorization_decision_id=uuid4(),
        request_id=uuid4(),
        tool_name="web.search",
        resource_type="research_query",
        resource_id="agent-identity",
    )


def test_authorized_invocation_verifies_before_provider_and_writes_correlation() -> None:
    order: list[str] = []
    audits: list[tuple] = []

    class Policy(GovernedWebToolPolicy):
        async def call(self, *_):
            order.append("provider")
            return SearchResponse(query="agent identity", results=[])

    class Authority:
        async def verify_execution(self, correlation):
            order.append("authority")
            return correlation

    async def audit(correlation, outcome, details):
        order.append("audit")
        audits.append((correlation, outcome, details))

    correlation = execution_correlation()
    host = GovernedWebMcpHost(
        policy=Policy(), correlated_audit_recorder=audit
    )

    result = asyncio.run(
        host.invoke_authorized(
            correlation,
            {"query": "agent identity", "max_results": 10},
            Authority(),
        )
    )

    assert result.query == "agent identity"
    assert order == ["authority", "provider", "audit"]
    assert audits[0][0] == correlation
    assert audits[0][1] == "succeeded"


def test_stale_authorization_stops_before_provider_invocation() -> None:
    called = False

    class Policy(GovernedWebToolPolicy):
        async def call(self, *_):
            nonlocal called
            called = True
            return SearchResponse(query="agent identity", results=[])

    class Authority:
        async def verify_execution(self, _):
            raise RuntimePlanError("Stored authorization is stale.")

    async def audit(*_):
        raise AssertionError("No tool execution occurred, so no execution audit is written.")

    host = GovernedWebMcpHost(
        policy=Policy(), correlated_audit_recorder=audit
    )

    with pytest.raises(RuntimePlanError, match="stale"):
        asyncio.run(
            host.invoke_authorized(
                execution_correlation(),
                {"query": "agent identity", "max_results": 10},
                Authority(),
            )
        )
    assert called is False
