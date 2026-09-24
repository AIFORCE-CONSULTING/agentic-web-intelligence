"""Tests for the first bounded agentic research planning contract."""

import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.agentic_research.contracts import (
    MAX_RESEARCH_TOPICS,
    TopicCoverageFacts,
    TopicPlan,
    TopicPlanValidationError,
    assess_topic_coverage,
    parse_topic_plan,
)
from app.agentic_research.planning import (
    TOPIC_PLANNING_PROMPT_VERSION,
    topic_planning_messages,
)
from app.agentic_research.store import AgenticResearchStore


def _topic(topic_id: str, topic: str, search_query: str) -> dict[str, str]:
    return {"topic_id": topic_id, "topic": topic, "search_query": search_query}


def test_valid_topic_plan_is_a_bounded_json_array() -> None:
    content = json.dumps(
        [
            _topic(
                "agent-identity",
                "How autonomous web agents establish and verify identity",
                "web agent identity authentication standards",
            ),
            _topic(
                "machine-interfaces",
                "How websites expose structured interfaces for autonomous agents",
                "WebMCP OpenAPI agent web interface standards",
            ),
        ]
    )

    plan = parse_topic_plan(content)

    assert [topic.topic_id for topic in plan.root] == [
        "agent-identity",
        "machine-interfaces",
    ]
    assert plan.root[0].topic.startswith("How autonomous web agents")


def test_topic_plan_schema_requires_one_to_three_items() -> None:
    schema = TopicPlan.model_json_schema()

    assert schema["type"] == "array"
    assert schema["minItems"] == 1
    assert schema["maxItems"] == MAX_RESEARCH_TOPICS
    assert schema["$defs"]["ResearchTopic"]["additionalProperties"] is False
    assert schema["$defs"]["ResearchTopic"]["required"] == [
        "topic_id",
        "topic",
        "search_query",
    ]


def test_more_than_three_topics_is_rejected() -> None:
    topics = [
        _topic(
            f"research-topic-{index}",
            f"Focused research topic number {index}",
            f"query {index}",
        )
        for index in range(1, 5)
    ]

    with pytest.raises(TopicPlanValidationError):
        parse_topic_plan(json.dumps(topics))


def test_duplicate_topic_ids_are_rejected() -> None:
    topics = [
        _topic("agent-trust", "How agent trust decisions are made", "agent trust decisions"),
        _topic("agent-trust", "How agent identity is established", "agent identity standards"),
    ]

    with pytest.raises(TopicPlanValidationError) as error:
        parse_topic_plan(json.dumps(topics))

    assert "unique" in str(error.value.__cause__)


@pytest.mark.parametrize(
    "content",
    [
        '{"topics": []}',
        "```json\n[]\n```",
        json.dumps(
            [
                _topic(
                    "Agent Identity",
                    "How autonomous agents establish identity",
                    "agent identity standards",
                )
            ]
        ),
        json.dumps(
            [
                {
                    **_topic(
                        "agent-identity",
                        "How autonomous agents establish identity",
                        "agent identity standards",
                    ),
                    "reason": "This topic matters.",
                }
            ]
        ),
    ],
)
def test_non_contract_model_output_is_rejected(content: str) -> None:
    with pytest.raises(TopicPlanValidationError):
        parse_topic_plan(content)


def test_prompt_asks_for_the_validated_contract() -> None:
    messages = topic_planning_messages("What will the future agentic web look like?")
    instruction = messages[0]["content"]

    assert TOPIC_PLANNING_PROMPT_VERSION == "agentic-research-topic-plan-v4"
    assert "between one and\nthree topics" in instruction
    assert '"topic_id"' in instruction
    assert '"topic"' in instruction
    assert "compare it with the operator's original question" in instruction
    assert "subject, requested comparison, constraint, and desired outcome" in instruction
    assert '"search_query"' in instruction
    assert messages[1] == {
        "role": "user",
        "content": "What will the future agentic web look like?",
    }


def test_empty_or_oversized_operator_question_is_rejected() -> None:
    with pytest.raises(ValueError, match="required"):
        topic_planning_messages("   ")
    with pytest.raises(ValueError, match="512"):
        topic_planning_messages("x" * 513)


def test_topic_coverage_requires_all_four_canonical_records() -> None:
    complete = TopicCoverageFacts(
        topic_record_id=uuid4(),
        evidence_id=uuid4(),
        trust_evaluation_id=uuid4(),
        relevance_decision_id=uuid4(),
        summary_artifact_id=uuid4(),
    )

    assert assess_topic_coverage(complete).counts_toward_topic is True

    fields = {
        "evidence_id": "evidence",
        "trust_evaluation_id": "trust",
        "relevance_decision_id": "relevance",
        "summary_artifact_id": "summary",
    }
    for field, requirement in fields.items():
        incomplete = complete.model_copy(update={field: None})
        assessment = assess_topic_coverage(incomplete)
        assert assessment.counts_toward_topic is False
        assert assessment.missing_requirements == [requirement]


def test_missing_topic_does_not_count_even_when_source_facts_exist() -> None:
    assessment = assess_topic_coverage(
        TopicCoverageFacts(
            evidence_id=uuid4(),
            trust_evaluation_id=uuid4(),
            relevance_decision_id=uuid4(),
            summary_artifact_id=uuid4(),
        )
    )

    assert assessment.counts_toward_topic is False


def test_topic_coverage_is_built_without_source_keywords() -> None:
    topic_record_id = uuid4()
    row = {
        "topic_id": "agent-identity",
        "topic": "How autonomous web agents establish and verify identity",
        "search_query": "web agent identity authentication standards",
        "source_url": "https://example.com/identity",
        "content_hash": "sha256:identity",
        "evidence_id": uuid4(),
        "trust_evaluation_id": uuid4(),
        "relevance_decision_id": uuid4(),
        "summary_artifact_id": uuid4(),
        "qualified_at": datetime.now(UTC),
        "topic_record_id": topic_record_id,
    }

    coverage = AgenticResearchStore._coverage_contracts([row])

    assert len(coverage) == 1
    assert coverage[0].status == "covered"
    assert coverage[0].evidence[0].source_url == "https://example.com/identity"
    assert "keywords" not in coverage[0].model_dump()


def test_topic_without_qualifying_evidence_is_uncovered() -> None:
    row = {
        "topic_id": "agent-identity",
        "topic": "How autonomous web agents establish and verify identity",
        "search_query": "web agent identity authentication standards",
        "source_url": None,
        "content_hash": None,
        "evidence_id": None,
        "trust_evaluation_id": None,
        "relevance_decision_id": None,
        "summary_artifact_id": None,
        "qualified_at": None,
    }

    coverage = AgenticResearchStore._coverage_contracts([row])

    assert coverage[0].status == "uncovered"
    assert coverage[0].evidence == []
