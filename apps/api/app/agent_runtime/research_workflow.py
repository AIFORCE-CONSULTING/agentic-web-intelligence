"""Canonical LangGraph structure for the topic-driven research workflow."""

from collections.abc import Awaitable, Callable
from typing import Literal, TypedDict
from uuid import UUID

from langgraph.graph import END, START, StateGraph

from app.agentic_research.contracts import ResearchTopic
from app.agentic_research.topic_planning import TopicPlanningService

MAX_GAP_SEARCH_ROUNDS = 2

ResearchStage = Literal[
    "requested",
    "topics_planned",
    "sources_discovered",
    "evidence_acquired",
    "relevance_decided",
    "summaries_stored",
    "coverage_complete",
    "coverage_incomplete",
    "awaiting_review",
    "report_stored",
    "completed",
    "failed",
    "cancelled",
]


class ResearchWorkflowState(TypedDict, total=False):
    """Bounded working context; PostgreSQL remains the official record."""

    workspace_id: UUID
    run_id: UUID
    question: str
    source_limit: int
    stage: ResearchStage
    topics: list[ResearchTopic]
    uncovered_topic_ids: list[str]
    gap_search_rounds: int
    failure_reason: str


ResearchNode = Callable[[ResearchWorkflowState], Awaitable[ResearchWorkflowState]]


def topic_planning_node(service: TopicPlanningService) -> ResearchNode:
    """Adapt the existing planning service to one LangGraph stage."""

    async def plan_topics(state: ResearchWorkflowState) -> ResearchWorkflowState:
        plan = await service.plan(
            state["workspace_id"],
            state["run_id"],
            state["question"],
        )
        return {"topics": plan.root, "stage": "topics_planned"}

    return plan_topics


class ResearchWorkflowNodes:
    """Typed platform operations used by the canonical research graph."""

    def __init__(
        self,
        *,
        plan_topics: ResearchNode,
        search_topics: ResearchNode,
        acquire_evidence: ResearchNode,
        evaluate_relevance: ResearchNode,
        summarize_evidence: ResearchNode,
        assess_topic_coverage: ResearchNode,
        search_missing_topic: ResearchNode,
        generate_final_report: ResearchNode,
        complete_research: ResearchNode,
    ) -> None:
        self.plan_topics = plan_topics
        self.search_topics = search_topics
        self.acquire_evidence = acquire_evidence
        self.evaluate_relevance = evaluate_relevance
        self.summarize_evidence = summarize_evidence
        self.assess_topic_coverage = assess_topic_coverage
        self.search_missing_topic = search_missing_topic
        self.generate_final_report = generate_final_report
        self.complete_research = complete_research


def _route_after_coverage(
    state: ResearchWorkflowState,
) -> Literal["search_missing_topic", "generate_final_report", "wait_for_review"]:
    if state.get("stage") == "awaiting_review":
        return "wait_for_review"
    uncovered = state.get("uncovered_topic_ids", [])
    rounds = state.get("gap_search_rounds", 0)
    if uncovered and rounds < MAX_GAP_SEARCH_ROUNDS:
        return "search_missing_topic"
    return "generate_final_report"


def build_research_workflow(nodes: ResearchWorkflowNodes) -> StateGraph:
    """Build the single topic-driven research graph without executing it."""

    async def wait_for_review(state: ResearchWorkflowState) -> ResearchWorkflowState:
        return {"stage": "awaiting_review"}

    graph = StateGraph(ResearchWorkflowState)
    graph.add_node("plan_topics", nodes.plan_topics)
    graph.add_node("search_topics", nodes.search_topics)
    graph.add_node("acquire_evidence", nodes.acquire_evidence)
    graph.add_node("evaluate_relevance", nodes.evaluate_relevance)
    graph.add_node("summarize_evidence", nodes.summarize_evidence)
    graph.add_node("assess_topic_coverage", nodes.assess_topic_coverage)
    graph.add_node("search_missing_topic", nodes.search_missing_topic)
    graph.add_node("generate_final_report", nodes.generate_final_report)
    graph.add_node("complete_research", nodes.complete_research)
    graph.add_node("wait_for_review", wait_for_review)

    graph.add_edge(START, "plan_topics")
    graph.add_edge("plan_topics", "search_topics")
    graph.add_edge("search_topics", "acquire_evidence")
    graph.add_edge("acquire_evidence", "evaluate_relevance")
    graph.add_edge("evaluate_relevance", "summarize_evidence")
    graph.add_edge("summarize_evidence", "assess_topic_coverage")
    graph.add_conditional_edges(
        "assess_topic_coverage",
        _route_after_coverage,
        {
            "search_missing_topic": "search_missing_topic",
            "generate_final_report": "generate_final_report",
            "wait_for_review": "wait_for_review",
        },
    )
    graph.add_edge("search_missing_topic", "acquire_evidence")
    graph.add_edge("generate_final_report", "complete_research")
    graph.add_edge("complete_research", END)
    graph.add_edge("wait_for_review", END)
    return graph
