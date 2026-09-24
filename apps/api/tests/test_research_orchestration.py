"""Tests for platform-owned agentic research workflow routing."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.agentic_research.orchestration import (
    ResearchOrchestrationService,
    ResearchOrchestrationSnapshot,
)


def snapshot(stage: str, **updates: object) -> ResearchOrchestrationSnapshot:
    values: dict[str, object] = {
        "workspace_id": uuid4(),
        "run_id": uuid4(),
        "stage": stage,
        "source_limit": 20,
        "gap_search_rounds": 0,
    }
    values.update(updates)
    return ResearchOrchestrationSnapshot.model_validate(values)


@pytest.mark.parametrize(
    ("stage", "expected_action"),
    [
        ("requested", "plan_topics"),
        ("topics_planned", "search_topics"),
        ("sources_discovered", "acquire_evidence"),
        ("evidence_acquired", "evaluate_relevance"),
        ("relevance_decided", "summarize_evidence"),
        ("summaries_stored", "assess_topic_coverage"),
        ("coverage_complete", "generate_final_report"),
        ("report_stored", "complete_research"),
    ],
)
def test_each_completed_stage_routes_to_one_next_action(
    stage: str, expected_action: str
) -> None:
    directive = ResearchOrchestrationService().next_action(snapshot(stage))

    assert directive.action == expected_action
    assert directive.topic_id is None
    assert directive.gap_search_round is None


def test_incomplete_coverage_routes_one_topic_to_the_next_gap_round() -> None:
    directive = ResearchOrchestrationService().next_action(
        snapshot(
            "coverage_incomplete",
            gap_search_rounds=1,
            uncovered_topic_ids=["agent-identity", "agent-provenance"],
        )
    )

    assert directive.action == "search_missing_topic"
    assert directive.topic_id == "agent-identity"
    assert directive.gap_search_round == 2


def test_exhausted_gap_searches_generate_an_explicitly_incomplete_report() -> None:
    directive = ResearchOrchestrationService().next_action(
        snapshot(
            "coverage_incomplete",
            gap_search_rounds=2,
            uncovered_topic_ids=["agent-identity"],
        )
    )

    assert directive.action == "generate_final_report"
    assert "disclose missing evidence" in directive.reason


def test_review_required_evidence_waits_for_the_existing_human_workflow() -> None:
    directive = ResearchOrchestrationService().next_action(snapshot("awaiting_review"))

    assert directive.action == "wait_for_human_review"
    assert "cannot enter automated model context" in directive.reason


@pytest.mark.parametrize("stage", ["completed", "failed", "cancelled"])
def test_terminal_tasks_do_not_request_more_work(stage: str) -> None:
    directive = ResearchOrchestrationService().next_action(snapshot(stage))

    assert directive.action == "none"


def test_snapshot_rejects_inconsistent_coverage_facts() -> None:
    with pytest.raises(ValidationError):
        snapshot("coverage_complete", uncovered_topic_ids=["still-missing"])

    with pytest.raises(ValidationError):
        snapshot("coverage_incomplete")


@pytest.mark.parametrize("source_limit", [4, 51])
def test_snapshot_rejects_source_limits_outside_the_operator_contract(
    source_limit: int,
) -> None:
    with pytest.raises(ValidationError):
        snapshot("requested", source_limit=source_limit)
