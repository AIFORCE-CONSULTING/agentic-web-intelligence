"""Tests for the canonical topic-driven LangGraph structure."""

import asyncio
from collections.abc import Callable
from uuid import uuid4

from app.agent_runtime.research_workflow import (
    ResearchWorkflowNodes,
    ResearchWorkflowState,
    build_research_workflow,
)


def node(
    name: str,
    visited: list[str],
    update: ResearchWorkflowState | None = None,
) -> Callable[[ResearchWorkflowState], object]:
    async def run(_: ResearchWorkflowState) -> ResearchWorkflowState:
        visited.append(name)
        return update or {}

    return run


def nodes(
    visited: list[str],
    *,
    coverage: ResearchWorkflowState,
    gap_result: ResearchWorkflowState | None = None,
) -> ResearchWorkflowNodes:
    async def assess_coverage(_: ResearchWorkflowState) -> ResearchWorkflowState:
        visited.append("assess_topic_coverage")
        if "search_missing_topic" in visited:
            return {"stage": "coverage_complete", "uncovered_topic_ids": []}
        return coverage

    return ResearchWorkflowNodes(
        plan_topics=node("plan_topics", visited, {"stage": "topics_planned"}),
        search_topics=node("search_topics", visited, {"stage": "sources_discovered"}),
        acquire_evidence=node("acquire_evidence", visited, {"stage": "evidence_acquired"}),
        evaluate_relevance=node(
            "evaluate_relevance", visited, {"stage": "relevance_decided"}
        ),
        summarize_evidence=node(
            "summarize_evidence", visited, {"stage": "summaries_stored"}
        ),
        assess_topic_coverage=assess_coverage,
        search_missing_topic=node(
            "search_missing_topic",
            visited,
            gap_result
            or {
                "stage": "evidence_acquired",
                "gap_search_rounds": 2,
                "uncovered_topic_ids": [],
            },
        ),
        generate_final_report=node(
            "generate_final_report", visited, {"stage": "report_stored"}
        ),
        complete_research=node("complete_research", visited, {"stage": "completed"}),
    )


def initial_state() -> ResearchWorkflowState:
    return {
        "workspace_id": uuid4(),
        "run_id": uuid4(),
        "question": "How should agents evaluate web evidence?",
        "source_limit": 20,
        "stage": "requested",
        "topics": [],
        "uncovered_topic_ids": [],
        "gap_search_rounds": 0,
    }


def test_complete_coverage_runs_each_research_stage_once() -> None:
    visited: list[str] = []
    workflow = build_research_workflow(
        nodes(visited, coverage={"stage": "coverage_complete", "uncovered_topic_ids": []})
    ).compile()

    result = asyncio.run(workflow.ainvoke(initial_state()))

    assert result["stage"] == "completed"
    assert visited == [
        "plan_topics",
        "search_topics",
        "acquire_evidence",
        "evaluate_relevance",
        "summarize_evidence",
        "assess_topic_coverage",
        "generate_final_report",
        "complete_research",
    ]


def test_missing_topic_uses_one_bounded_gap_search_before_reporting() -> None:
    visited: list[str] = []
    workflow = build_research_workflow(
        nodes(
            visited,
            coverage={
                "stage": "coverage_incomplete",
                "gap_search_rounds": 1,
                "uncovered_topic_ids": ["agent-identity"],
            },
        )
    ).compile()

    result = asyncio.run(workflow.ainvoke(initial_state()))

    assert result["stage"] == "completed"
    assert visited.count("search_missing_topic") == 1
    assert visited.count("acquire_evidence") == 2
    assert result["gap_search_rounds"] == 2


def test_exhausted_gap_limit_generates_report_without_another_search() -> None:
    visited: list[str] = []
    workflow = build_research_workflow(
        nodes(
            visited,
            coverage={
                "stage": "coverage_incomplete",
                "gap_search_rounds": 2,
                "uncovered_topic_ids": ["agent-identity"],
            },
        )
    ).compile()

    result = asyncio.run(workflow.ainvoke(initial_state()))

    assert result["stage"] == "completed"
    assert "search_missing_topic" not in visited


def test_review_required_evidence_stops_before_report_generation() -> None:
    visited: list[str] = []
    workflow = build_research_workflow(
        nodes(visited, coverage={"stage": "awaiting_review"})
    ).compile()

    result = asyncio.run(workflow.ainvoke(initial_state()))

    assert result["stage"] == "awaiting_review"
    assert "generate_final_report" not in visited
    assert "complete_research" not in visited
