"""Initial model-visible capabilities for governed agentic research."""

from collections.abc import Iterable, Mapping
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.web_research.contracts import ExtractRequest, SearchRequest
from app.web_research.mcp_host import GovernedWebToolPolicy

RESEARCH_CAPABILITY_CATALOG_VERSION = "agentic-research-capabilities-v1"
INITIAL_RESEARCH_CAPABILITIES = ("web.search", "web.extract")

ResearchCapabilityName = Literal["web.search", "web.extract"]


class ResearchCapabilityError(ValueError):
    """Raised when a model proposal falls outside the current research grant."""


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


class ValidatedCapabilityRequest(BaseModel):
    """A model proposal that passed catalog, grant, argument, and source checks."""

    model_config = ConfigDict(extra="forbid")

    catalog_version: str
    capability: ResearchCapabilityName
    arguments: dict[str, Any]


class AgentResearchCapabilityCatalog:
    """Expose and validate the narrow initial catalog without executing tools."""

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

    def catalog(
        self, granted_capabilities: Iterable[str]
    ) -> ResearchCapabilityCatalog:
        """Return only initial capabilities granted to the current task step."""

        granted = set(granted_capabilities)
        capabilities = [
            self._definitions[name]
            for name in INITIAL_RESEARCH_CAPABILITIES
            if name in granted
        ]
        if not capabilities:
            raise ResearchCapabilityError(
                "The current research step has no granted research capabilities."
            )
        return ResearchCapabilityCatalog(capabilities=capabilities)

    def validate_request(
        self,
        capability: str,
        arguments: Mapping[str, object],
        granted_capabilities: Iterable[str],
        discovered_source_urls: Iterable[str] = (),
    ) -> ValidatedCapabilityRequest:
        """Validate one proposal before trusted orchestration can consider execution."""

        if capability not in self._definitions:
            raise ResearchCapabilityError(
                f"Capability '{capability}' is not in the research capability catalog."
            )
        if capability not in set(granted_capabilities):
            raise ResearchCapabilityError(
                f"Capability '{capability}' is not granted to the current research step."
            )

        try:
            if capability == "web.search":
                validated = SearchRequest.model_validate(arguments, extra="forbid")
            else:
                validated = ExtractRequest.model_validate(arguments, extra="forbid")
        except ValidationError as error:
            raise ResearchCapabilityError(
                f"Capability '{capability}' received invalid arguments."
            ) from error

        normalized = validated.model_dump(mode="json")
        if capability == "web.extract" and validated.url not in set(discovered_source_urls):
            raise ResearchCapabilityError(
                "Evidence may be acquired only from a source discovered for this research task."
            )
        return ValidatedCapabilityRequest(
            catalog_version=RESEARCH_CAPABILITY_CATALOG_VERSION,
            capability=capability,
            arguments=normalized,
        )
