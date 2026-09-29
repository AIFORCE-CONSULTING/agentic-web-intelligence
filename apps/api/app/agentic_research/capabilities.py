"""Initial model-visible capabilities for governed agentic research."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.web_research.mcp_host import GovernedWebToolPolicy

RESEARCH_CAPABILITY_CATALOG_VERSION = "agentic-research-capabilities-v1"
INITIAL_RESEARCH_CAPABILITIES = ("web.search", "web.extract")

ResearchCapabilityName = Literal["web.search", "web.extract"]


class ResearchCapabilityDefinition(BaseModel):
    """One model-visible capability derived from the governed MCP registry."""

    model_config = ConfigDict(extra="forbid")

    name: ResearchCapabilityName
    description: str
    input_schema: dict[str, Any]
    output_contract: str


class ResearchCapabilityCatalog(BaseModel):
    """Versioned capability set that may be shown to a research model."""

    model_config = ConfigDict(extra="forbid")

    version: str = RESEARCH_CAPABILITY_CATALOG_VERSION
    capabilities: list[ResearchCapabilityDefinition] = Field(min_length=1, max_length=2)


class AgentResearchCapabilityCatalog:
    """Expose model-facing schemas; RuntimeService owns authorization."""

    def __init__(self, policy: GovernedWebToolPolicy | None = None) -> None:
        self._policy = policy or GovernedWebToolPolicy()
        registered = {tool.name: tool for tool in self._policy.registry().tools}
        missing = [name for name in INITIAL_RESEARCH_CAPABILITIES if name not in registered]
        if missing:
            raise RuntimeError(f"The governed MCP registry is missing: {', '.join(missing)}")
        self._definitions = {
            name: ResearchCapabilityDefinition(
                name=name,
                description=registered[name].purpose,
                input_schema=registered[name].input_schema,
                output_contract=registered[name].output_contract,
            )
            for name in INITIAL_RESEARCH_CAPABILITIES
        }

    def catalog(self) -> ResearchCapabilityCatalog:
        """Return schemas only; availability never implies permission to execute."""

        return ResearchCapabilityCatalog(
            capabilities=[
                self._definitions[name] for name in INITIAL_RESEARCH_CAPABILITIES
            ]
        )
