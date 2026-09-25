"""Typed LangGraph nodes backed by the platform's existing research services."""

from collections.abc import Awaitable, Callable

from app.agent_runtime.research_workflow import (
    ResearchNode,
    ResearchWorkflowNodes,
    ResearchWorkflowState,
    topic_planning_node,
)
from app.agentic_research.contracts import TopicSourceAssociation
from app.agentic_research.control import AgenticResearchControlService
from app.agentic_research.relevance import TopicRelevanceService
from app.agentic_research.reporting import ResearchReportingService
from app.agentic_research.store import AgenticResearchStore
from app.agentic_research.topic_planning import TopicPlanningService
from app.evidence_summaries.service import EvidenceSummaryAutomation
from app.web_research.contracts import SearchResponse, SourceCandidate
from app.web_research.store import ResearchStore
from app.web_research.workflow import run_search_workflow
from app.web_trust.preflight import (
    DIRECT_PREFLIGHT_SOURCE_LIMIT,
    CandidatePreflightService,
    CandidatePreflightTemporalBoundary,
)

Search = Callable[[str, int], Awaitable[SearchResponse]]


def topic_search_node(
    control: AgenticResearchControlService,
    research_store: ResearchStore,
    agentic_store: AgenticResearchStore,
    search: Search = run_search_workflow,
) -> ResearchNode:
    """Search every planned topic and store at most the task-wide source limit."""

    async def search_topics(state: ResearchWorkflowState) -> ResearchWorkflowState:
        pools: list[tuple[str, SearchResponse]] = []
        for topic in state["topics"]:
            decision = await control.consider_request(
                state["workspace_id"],
                state["run_id"],
                topic.topic_id,
                "web.search",
                {"query": topic.search_query, "max_results": state["source_limit"]},
                {"web.search"},
            )
            if decision.decision == "accepted":
                pools.append(
                    (topic.topic_id, await search(topic.search_query, state["source_limit"]))
                )

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
) -> ResearchNode:
    """Apply the existing direct-versus-Temporal preflight boundary."""

    async def acquire(state: ResearchWorkflowState) -> ResearchWorkflowState:
        urls = state.get("new_source_urls", [])
        if not urls:
            return {"stage": "evidence_acquired"}
        if len(urls) <= DIRECT_PREFLIGHT_SOURCE_LIMIT:
            await direct.preflight_run(state["workspace_id"], state["run_id"], urls)
            return {"stage": "evidence_acquired"}
        await temporal.schedule(state["run_id"], urls)
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
            state["workspace_id"], state["run_id"], urls
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
    control: AgenticResearchControlService,
    research_store: ResearchStore,
    agentic_store: AgenticResearchStore,
    reporting: ResearchReportingService,
    search: Search = run_search_workflow,
) -> ResearchNode:
    """Use one reserved gap round to search the first uncovered planned topic."""

    async def search_gap(state: ResearchWorkflowState) -> ResearchWorkflowState:
        control_state = await control.begin_gap_search_round(
            state["workspace_id"], state["run_id"]
        )
        if control_state is None:
            return {"gap_search_rounds": 2, "new_source_urls": []}
        remaining_capacity = max(
            0,
            state["source_limit"] - state.get("discovered_source_count", 0),
        )
        if remaining_capacity == 0:
            return {
                "gap_search_rounds": control_state.gap_search_rounds,
                "new_source_urls": [],
            }
        topic_id = state["uncovered_topic_ids"][0]
        topic = next(item for item in state["topics"] if item.topic_id == topic_id)
        prior_queries = [item.search_query for item in state["topics"]]
        query = await reporting.missing_topic_query(
            state["workspace_id"], topic, prior_queries
        )
        decision = await control.consider_request(
            state["workspace_id"], state["run_id"], topic_id, "web.search",
            {"query": query, "max_results": remaining_capacity}, {"web.search"},
            purpose="gap",
        )
        if decision.decision != "accepted":
            return {"gap_search_rounds": control_state.gap_search_rounds, "new_source_urls": []}
        response = await search(query, remaining_capacity)
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
        await agentic_store.record_discovered_sources(
            state["workspace_id"], state["run_id"], associations
        )
        return {
            "gap_search_rounds": control_state.gap_search_rounds,
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


def platform_research_nodes(
    *,
    topic_planning: TopicPlanningService,
    control: AgenticResearchControlService,
    research_store: ResearchStore,
    agentic_store: AgenticResearchStore,
    preflight: CandidatePreflightService,
    preflight_temporal: CandidatePreflightTemporalBoundary,
    relevance: TopicRelevanceService,
    summaries: EvidenceSummaryAutomation,
    reporting: ResearchReportingService,
    search: Search = run_search_workflow,
) -> ResearchWorkflowNodes:
    """Bind the canonical graph to the platform's existing service owners."""

    return ResearchWorkflowNodes(
        plan_topics=topic_planning_node(topic_planning),
        search_topics=topic_search_node(control, research_store, agentic_store, search),
        acquire_evidence=evidence_acquisition_node(preflight, preflight_temporal),
        evaluate_relevance=topic_relevance_node(
            research_store, agentic_store, relevance
        ),
        summarize_evidence=evidence_summary_node(summaries),
        assess_topic_coverage=topic_coverage_node(research_store, agentic_store),
        search_missing_topic=missing_topic_search_node(
            control, research_store, agentic_store, reporting, search
        ),
        generate_final_report=final_report_node(reporting),
        complete_research=completion_node(),
    )
