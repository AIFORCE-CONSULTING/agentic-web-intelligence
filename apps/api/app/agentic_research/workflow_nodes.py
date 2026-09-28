"""Typed LangGraph nodes backed by the platform's existing research services."""

from collections.abc import Awaitable, Callable, Mapping
from typing import Any, Protocol, cast
from uuid import UUID, uuid4

from app.agent_runtime.contracts import (
    CapabilityRequest,
    McpExecutionCorrelation,
    RuntimeRun,
)
from app.agent_runtime.research_workflow import (
    ResearchNode,
    ResearchWorkflowNodes,
    ResearchWorkflowState,
    topic_planning_node,
)
from app.agentic_research.contracts import TopicSourceAssociation
from app.agentic_research.relevance import TopicRelevanceService
from app.agentic_research.reporting import ResearchReportingService
from app.agentic_research.store import AgenticResearchStore
from app.agentic_research.topic_planning import TopicPlanningService
from app.durable_execution.contracts import (
    WorkflowContinuationContext,
    WorkflowThreadReference,
)
from app.evidence_summaries.service import EvidenceSummaryAutomation
from app.web_research.contracts import (
    Evidence,
    SearchResponse,
    SourceCandidate,
    ToolProviderError,
)
from app.web_research.store import ResearchStore
from app.web_trust.preflight import (
    DIRECT_PREFLIGHT_SOURCE_LIMIT,
    CandidatePreflightService,
    CandidatePreflightTemporalBoundary,
)

Search = Callable[[str, int], Awaitable[SearchResponse]]


def _continuation_context(state: ResearchWorkflowState) -> WorkflowContinuationContext:
    return WorkflowContinuationContext(
        thread=WorkflowThreadReference(
            research_run_id=str(state["run_id"]),
            workspace_id=str(state["workspace_id"]),
            thread_id=str(state["run_id"]),
        ),
        expected_research_status=state.get("canonical_status", state["stage"]),
        expected_status_version=state.get("status_version", 0),
    )


class ResearchAuthority(Protocol):
    """RuntimeService operations used by governed research nodes."""

    async def ensure_research_assignment(
        self, workspace_id: UUID, research_run_id: UUID, goal: str
    ) -> RuntimeRun: ...

    async def authorize_request(self, request: CapabilityRequest) -> Any: ...

    async def register_discovered_source(
        self, research_run_id: UUID, topic_id: str, source_url: str, source_limit: int
    ) -> bool: ...

    async def begin_gap_search_round(self, research_run_id: UUID) -> int | None: ...


class GovernedMcpInvoker(Protocol):
    """Governed MCP invocation used after RuntimeService authorization."""

    async def invoke_authorized(
        self,
        correlation: McpExecutionCorrelation,
        arguments: Mapping[str, Any],
        authority: Any,
    ) -> SearchResponse | Evidence: ...


async def _authorized_search(
    state: ResearchWorkflowState,
    topic_id: str,
    query: str,
    max_results: int,
    purpose: str,
    authority: ResearchAuthority,
    mcp: GovernedMcpInvoker,
    research_store: ResearchStore,
) -> SearchResponse | None:
    research = await research_store.get_run(state["workspace_id"], state["run_id"])
    if research is None:
        raise KeyError(state["run_id"])
    assignment = await authority.ensure_research_assignment(
        state["workspace_id"], state["run_id"], state["question"]
    )
    step = next(
        (
            item
            for item in assignment.steps
            if item.role == "researcher" and item.status == "active"
        ),
        None,
    )
    if step is None:
        raise RuntimeError("The research assignment has no active researcher step.")
    request_id = uuid4()
    arguments: dict[str, object] = {"query": query, "max_results": max_results}
    request = CapabilityRequest(
        workspace_id=state["workspace_id"],
        runtime_run_id=assignment.id,
        runtime_step_id=step.id,
        research_run_id=state["run_id"],
        research_status=research.status,
        research_status_version=research.status_version,
        topic_id=topic_id,
        action="web.search",
        resource_type="research_query",
        resource_id=query,
        arguments=arguments,
        request_id=request_id,
        purpose=purpose,
    )
    decision = await authority.authorize_request(request)
    if decision.decision != "allow":
        return None
    try:
        result = await mcp.invoke_authorized(
            McpExecutionCorrelation(
                workspace_id=request.workspace_id,
                research_run_id=request.research_run_id,
                runtime_run_id=request.runtime_run_id,
                runtime_step_id=request.runtime_step_id,
                authorization_decision_id=decision.id,
                request_id=request.request_id,
                tool_name=request.action,
                resource_type=request.resource_type,
                resource_id=request.resource_id,
            ),
            arguments,
            authority,
        )
    except ToolProviderError:
        await research_store.transition_status(
            state["run_id"],
            research.status,
            research.status_version,
            "failed",
            uuid4(),
            "The governed web-search provider is unavailable.",
            failed_stage=research.status,
            failure_code="search_unavailable",
            failure_explanation="The web-search provider is temporarily unavailable.",
            retryable=True,
        )
        raise
    return cast(SearchResponse, result)


def topic_search_node(
    authority: ResearchAuthority,
    mcp: GovernedMcpInvoker,
    research_store: ResearchStore,
    agentic_store: AgenticResearchStore,
) -> ResearchNode:
    """Search every planned topic and store at most the task-wide source limit."""

    async def search_topics(state: ResearchWorkflowState) -> ResearchWorkflowState:
        pools: list[tuple[str, SearchResponse]] = []
        for topic in state["topics"]:
            response = await _authorized_search(
                state,
                topic.topic_id,
                topic.search_query,
                state["source_limit"],
                "initial",
                authority,
                mcp,
                research_store,
            )
            if response is not None:
                pools.append((topic.topic_id, response))

        selected: list[tuple[str, object, int]] = []
        seen: set[str] = set()
        position = 0
        while len(selected) < state["source_limit"]:
            added = False
            for topic_id, response in pools:
                if position >= len(response.results):
                    continue
                result = response.results[position]
                added = True
                if result.url not in seen:
                    seen.add(result.url)
                    selected.append((topic_id, result, position + 1))
                    if len(selected) == state["source_limit"]:
                        break
            if not added:
                break
            position += 1

        candidates = [
            SourceCandidate(rank=index, **result.model_dump())
            for index, (_, result, _) in enumerate(selected, start=1)
        ]
        stored = await research_store.save_new_sources(
            state["run_id"], candidates, state["source_limit"]
        )
        stored_urls = {source.url for source in stored}
        associations = [
            TopicSourceAssociation(
                topic_id=topic_id, source_url=result.url, result_rank=result_rank
            )
            for topic_id, response in pools
            for result_rank, result in enumerate(response.results, start=1)
            if result.url in stored_urls
        ]
        registered_urls: set[tuple[str, str]] = set()
        for association in associations:
            identity = (association.topic_id, association.source_url)
            if identity in registered_urls:
                continue
            registered_urls.add(identity)
            await authority.register_discovered_source(
                state["run_id"],
                association.topic_id,
                association.source_url,
                state["source_limit"],
            )
        await agentic_store.record_discovered_sources(
            state["workspace_id"], state["run_id"], associations
        )
        return {
            "stage": "sources_discovered",
            "new_source_urls": [source.url for source in stored],
            "discovered_source_count": len(stored),
            "source_topics": associations,
        }

    return search_topics


def evidence_acquisition_node(
    direct: CandidatePreflightService,
    temporal: CandidatePreflightTemporalBoundary,
    authority: ResearchAuthority,
    mcp: GovernedMcpInvoker,
) -> ResearchNode:
    """Apply the existing direct-versus-Temporal preflight boundary."""

    async def acquire(state: ResearchWorkflowState) -> ResearchWorkflowState:
        urls = state.get("new_source_urls", [])
        if not urls:
            return {"stage": "evidence_acquired"}
        if len(urls) <= DIRECT_PREFLIGHT_SOURCE_LIMIT:
            await direct.preflight_run_authorized(
                state["workspace_id"], state["run_id"], authority, mcp, urls
            )
            return {"stage": "evidence_acquired"}
        await temporal.schedule(
            state["run_id"], urls, _continuation_context(state)
        )
        return {"stage": "awaiting_preflight"}

    return acquire


def topic_relevance_node(
    research_store: ResearchStore,
    agentic_store: AgenticResearchStore,
    relevance: TopicRelevanceService,
) -> ResearchNode:
    """Evaluate only trust-eligible evidence against its originating topics."""

    async def evaluate(state: ResearchWorkflowState) -> ResearchWorkflowState:
        run = await research_store.get_run(state["workspace_id"], state["run_id"])
        if run is None:
            raise KeyError(state["run_id"])
        associations = state.get("source_topics") or await agentic_store.list_discovered_sources(
            state["workspace_id"], state["run_id"]
        )
        candidates = {source.url: source for source in run.sources}
        relevant: list[TopicSourceAssociation] = []
        for association in associations:
            source = candidates.get(association.source_url)
            if source is None or source.preflight_status != "ready_to_extract":
                continue
            if source.preflight_content_hash is None:
                continue
            decision = await relevance.evaluate(
                state["workspace_id"],
                state["run_id"],
                association.topic_id,
                source.preflight_final_url or source.url,
                source.preflight_content_hash,
            )
            if decision.decision == "relevant":
                relevant.append(association)
        return {"stage": "relevance_decided", "relevant_sources": relevant}

    return evaluate


def evidence_summary_node(automation: EvidenceSummaryAutomation) -> ResearchNode:
    """Start the existing summary automation for relevant source URLs only."""

    async def summarize(state: ResearchWorkflowState) -> ResearchWorkflowState:
        urls = list(dict.fromkeys(item.source_url for item in state.get("relevant_sources", [])))
        if not urls:
            return {"stage": "summaries_stored"}
        execution = await automation.start_for_urls(
            state["workspace_id"],
            state["run_id"],
            urls,
            _continuation_context(state),
        )
        return {
            "stage": (
                "summaries_stored" if execution.status == "completed" else "awaiting_summaries"
            )
        }

    return summarize


def topic_coverage_node(
    research_store: ResearchStore, agentic_store: AgenticResearchStore
) -> ResearchNode:
    """Qualify stored summaries and report which planned topics remain uncovered."""

    async def assess(state: ResearchWorkflowState) -> ResearchWorkflowState:
        run = await research_store.get_run(state["workspace_id"], state["run_id"])
        if run is None:
            raise KeyError(state["run_id"])
        candidates = {source.url: source for source in run.sources}
        for association in state.get("relevant_sources", []):
            source = candidates.get(association.source_url)
            if source is not None and source.preflight_content_hash is not None:
                await agentic_store.qualify_evidence(
                    state["workspace_id"], state["run_id"], association.topic_id,
                    source.preflight_final_url or source.url, source.preflight_content_hash,
                )
        coverage = await agentic_store.list_topic_coverage(
            state["workspace_id"], state["run_id"]
        )
        uncovered = [topic.topic_id for topic in coverage if topic.status == "uncovered"]
        return {
            "stage": "coverage_incomplete" if uncovered else "coverage_complete",
            "uncovered_topic_ids": uncovered,
        }

    return assess


def missing_topic_search_node(
    authority: ResearchAuthority,
    mcp: GovernedMcpInvoker,
    research_store: ResearchStore,
    agentic_store: AgenticResearchStore,
    reporting: ResearchReportingService,
) -> ResearchNode:
    """Use one reserved gap round to search the first uncovered planned topic."""

    async def search_gap(state: ResearchWorkflowState) -> ResearchWorkflowState:
        gap_round = await authority.begin_gap_search_round(state["run_id"])
        if gap_round is None:
            return {"gap_search_rounds": 2, "new_source_urls": []}
        remaining_capacity = max(
            0,
            state["source_limit"] - state.get("discovered_source_count", 0),
        )
        if remaining_capacity == 0:
            return {
                "gap_search_rounds": gap_round,
                "new_source_urls": [],
            }
        topic_id = state["uncovered_topic_ids"][0]
        topic = next(item for item in state["topics"] if item.topic_id == topic_id)
        prior_queries = [item.search_query for item in state["topics"]]
        query = await reporting.missing_topic_query(
            state["workspace_id"], topic, prior_queries
        )
        response = await _authorized_search(
            state,
            topic_id,
            query,
            remaining_capacity,
            "gap",
            authority,
            mcp,
            research_store,
        )
        if response is None:
            return {"gap_search_rounds": gap_round, "new_source_urls": []}
        candidates = [
            SourceCandidate(rank=index, **result.model_dump())
            for index, result in enumerate(response.results, start=1)
        ]
        stored = await research_store.save_new_sources(
            state["run_id"], candidates, remaining_capacity
        )
        associations = [
            TopicSourceAssociation(topic_id=topic_id, source_url=item.url, result_rank=item.rank)
            for item in stored
        ]
        for association in associations:
            await authority.register_discovered_source(
                state["run_id"], topic_id, association.source_url, state["source_limit"]
            )
        await agentic_store.record_discovered_sources(
            state["workspace_id"], state["run_id"], associations
        )
        return {
            "gap_search_rounds": gap_round,
            "new_source_urls": [item.url for item in stored],
            "discovered_source_count": state.get("discovered_source_count", 0) + len(stored),
            "source_topics": associations,
        }

    return search_gap


def final_report_node(reporting: ResearchReportingService) -> ResearchNode:
    """Generate and store the report from qualified summaries only."""

    async def report(state: ResearchWorkflowState) -> ResearchWorkflowState:
        await reporting.final_report(
            state["workspace_id"], state["run_id"], state["question"]
        )
        return {"stage": "report_stored"}

    return report


def completion_node() -> ResearchNode:
    """Mark the in-memory graph outcome after the report is durably stored."""

    async def complete(state: ResearchWorkflowState) -> ResearchWorkflowState:
        return {"stage": "completed"}

    return complete


def durable_failure_node() -> ResearchNode:
    """Retain the typed durable failure for the graph-owned status transition."""

    async def fail(state: ResearchWorkflowState) -> ResearchWorkflowState:
        return {
            "stage": "failed",
            "failure_code": state.get("failure_code", "durable_work_failed"),
            "failure_explanation": state.get(
                "failure_explanation", "Required background processing did not complete."
            ),
            "retryable": state.get("retryable", True),
        }

    return fail


def platform_research_nodes(
    *,
    topic_planning: TopicPlanningService,
    authority: ResearchAuthority,
    mcp: GovernedMcpInvoker,
    research_store: ResearchStore,
    agentic_store: AgenticResearchStore,
    preflight: CandidatePreflightService,
    preflight_temporal: CandidatePreflightTemporalBoundary,
    relevance: TopicRelevanceService,
    summaries: EvidenceSummaryAutomation,
    reporting: ResearchReportingService,
) -> ResearchWorkflowNodes:
    """Bind the canonical graph to the platform's existing service owners."""

    return ResearchWorkflowNodes(
        plan_topics=topic_planning_node(topic_planning),
        search_topics=topic_search_node(authority, mcp, research_store, agentic_store),
        acquire_evidence=evidence_acquisition_node(
            preflight, preflight_temporal, authority, mcp
        ),
        evaluate_relevance=topic_relevance_node(
            research_store, agentic_store, relevance
        ),
        summarize_evidence=evidence_summary_node(summaries),
        assess_topic_coverage=topic_coverage_node(research_store, agentic_store),
        search_missing_topic=missing_topic_search_node(
            authority, mcp, research_store, agentic_store, reporting
        ),
        generate_final_report=final_report_node(reporting),
        complete_research=completion_node(),
        fail_durable_work=durable_failure_node(),
    )
