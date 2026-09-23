"""Application-owned checks for model-proposed research actions."""

from collections.abc import Iterable, Mapping
from typing import Literal
from uuid import UUID

from app.agentic_research.capabilities import (
    AgentResearchCapabilityCatalog,
    ResearchCapabilityError,
)
from app.agentic_research.contracts import (
    CapabilityDecision,
    CapabilityRequestDecision,
    ResearchControlState,
)
from app.agentic_research.store import AgenticResearchStore


class AgenticResearchControlService:
    """Check, limit, and record proposed actions without executing them."""

    def __init__(
        self,
        store: AgenticResearchStore,
        catalog: AgentResearchCapabilityCatalog | None = None,
    ) -> None:
        self._store = store
        self._catalog = catalog or AgentResearchCapabilityCatalog()

    async def consider_request(
        self,
        workspace_id: UUID,
        run_id: UUID,
        topic_id: str,
        capability: str,
        arguments: Mapping[str, object],
        granted_capabilities: Iterable[str],
        discovered_source_urls: Iterable[str] = (),
        purpose: Literal["initial", "gap"] = "initial",
    ) -> CapabilityRequestDecision:
        """Accept one safe, nonrepeated proposal or record why it was denied."""

        state = await self._store.control_state(workspace_id, run_id)
        try:
            request = self._catalog.validate_request(
                capability,
                arguments,
                granted_capabilities,
                discovered_source_urls,
            )
        except ResearchCapabilityError as error:
            return await self._record(
                workspace_id,
                run_id,
                topic_id,
                capability,
                arguments,
                state,
                "denied",
                str(error),
            )

        if request.capability == "web.search":
            accepted = await self._store.reserve_search_query(
                workspace_id,
                run_id,
                topic_id,
                str(request.arguments["query"]),
                purpose,
            )
            if not accepted:
                return await self._record(
                    workspace_id,
                    run_id,
                    topic_id,
                    request.capability,
                    request.arguments,
                    state,
                    "denied",
                    "This search query has already been used for the research task.",
                )
        else:
            accepted = await self._store.reserve_source_attempt(
                workspace_id,
                run_id,
                topic_id,
                str(request.arguments["url"]),
            )
            if not accepted:
                return await self._record(
                    workspace_id,
                    run_id,
                    topic_id,
                    request.capability,
                    request.arguments,
                    state,
                    "denied",
                    "The evidence-acquisition attempt limit has been reached for this source.",
                )
        return await self._record(
            workspace_id,
            run_id,
            topic_id,
            request.capability,
            request.arguments,
            state,
            "accepted",
            "The platform checks accepted this research request.",
        )

    async def begin_gap_search_round(
        self, workspace_id: UUID, run_id: UUID
    ) -> ResearchControlState | None:
        """Allow at most two additional rounds for topics that still lack evidence."""

        return await self._store.begin_gap_search_round(workspace_id, run_id)

    async def _record(
        self,
        workspace_id: UUID,
        run_id: UUID,
        topic_id: str,
        capability: str,
        arguments: Mapping[str, object],
        state: ResearchControlState,
        outcome: CapabilityDecision,
        reason: str,
    ) -> CapabilityRequestDecision:
        decision = CapabilityRequestDecision(
            decision=outcome,
            reason=reason,
            capability=capability[:128],
            arguments=self._safe_audit_arguments(capability, arguments),
            gap_search_rounds=state.gap_search_rounds,
        )
        await self._store.record_capability_decision(
            workspace_id, run_id, topic_id, decision
        )
        return decision

    @staticmethod
    def _safe_audit_arguments(
        capability: str, arguments: Mapping[str, object]
    ) -> dict[str, object]:
        """Keep useful request facts without retaining arbitrary submitted values."""

        safe: dict[str, object] = {"argument_names": sorted(arguments)[:20]}
        if capability == "web.search":
            query = arguments.get("query")
            max_results = arguments.get("max_results")
            if isinstance(query, str):
                safe["query"] = query[:512]
            if isinstance(max_results, int) and not isinstance(max_results, bool):
                safe["max_results"] = max_results
        elif capability == "web.extract":
            url = arguments.get("url")
            if isinstance(url, str):
                safe["url"] = url[:2_048]
        return safe
