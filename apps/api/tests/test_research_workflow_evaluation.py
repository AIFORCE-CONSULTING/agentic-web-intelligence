"""Tests for the complete offline agentic research workflow evaluation."""

import asyncio
import json

from app.agent_evaluations.research_fixtures import (
    RESEARCH_FIXTURE_VERSION,
    RESEARCH_FIXTURES,
    RESEARCH_SUITE_VERSION,
)
from app.agent_evaluations.research_runner import (
    PROMPT_VERSIONS,
    RESEARCH_SETTINGS_VERSION,
    THINKING_BY_STAGE,
    ResearchModelIdentity,
    ResearchModelResponse,
    _messages_for,
    evaluate_fixture,
    run_research_evaluation,
)

MODEL_OUTPUTS = {
    "plan-focused-topics": json.dumps(
        [
            {
                "topic_id": "agent-identity",
                "topic": "How websites establish identity for autonomous research agents",
                "search_query": "website identity standards for autonomous agents",
            }
        ]
    ),
    "accept-relevant-evidence": "YES",
    "reject-irrelevant-evidence": "NO",
    "ignore-hostile-webpage-instruction": "NO",
    "reject-weak-topic-mention": "NO",
    "ignore-hostile-role-change": "NO",
    "accept-detailed-relevant-evidence": "YES",
    "search-for-missing-topic": "website identity standards for research agents",
    "ground-final-report": (
        "## agent-identity\nSigned provenance can identify the publisher "
        "[[source-c2pa-001]]."
    ),
}


def model_response(content: str) -> ResearchModelResponse:
    return ResearchModelResponse(
        content=content,
        thinking="reasoning",
        prompt_token_count=100,
        generated_token_count=20,
        total_duration_ns=1_000,
        load_duration_ns=100,
        prompt_duration_ns=300,
        generation_duration_ns=600,
    )


def test_complete_fixture_matrix_passes_with_expected_model_responses() -> None:
    called: list[str] = []

    async def respond(fixture: object) -> ResearchModelResponse:
        fixture_id = fixture.id
        called.append(fixture_id)
        return model_response(MODEL_OUTPUTS[fixture_id])

    report = asyncio.run(
        run_research_evaluation(
            respond,
            RESEARCH_FIXTURES,
            "mock-research-model",
            iterations=3,
            model_identity=ResearchModelIdentity(digest="sha256:test", size_bytes=1234),
        )
    )

    assert report.passed
    assert report.passed_case_count == report.case_count == len(RESEARCH_FIXTURES)
    assert set(called) == set(MODEL_OUTPUTS)
    assert report.suite_version == RESEARCH_SUITE_VERSION
    assert report.fixture_version == RESEARCH_FIXTURE_VERSION
    assert report.prompt_versions == PROMPT_VERSIONS
    assert report.settings_version == RESEARCH_SETTINGS_VERSION
    assert report.iterations == 3
    assert report.model_digest == "sha256:test"
    assert all(result.passed_attempt_count == 3 for result in report.results)
    model_attempt = next(
        result.attempts[0] for result in report.results if result.check_owner == "model"
    )
    assert model_attempt.prompt_token_count == 100
    assert model_attempt.generated_token_count == 20
    assert model_attempt.thinking_enabled == THINKING_BY_STAGE[model_attempt.stage]


def test_topic_planning_uses_the_exact_array_schema_not_generic_json_mode() -> None:
    fixture = next(item for item in RESEARCH_FIXTURES if item.id == "plan-focused-topics")

    _, response_format = _messages_for(fixture)

    assert isinstance(response_format, dict)
    assert response_format["type"] == "array"
    assert response_format["minItems"] == 1
    assert response_format["maxItems"] == 3


def test_topic_planning_gets_only_one_bounded_coverage_correction() -> None:
    fixture = next(item for item in RESEARCH_FIXTURES if item.id == "plan-focused-topics")
    calls = 0

    async def respond(current: object) -> ResearchModelResponse:
        nonlocal calls
        calls += 1
        if "coverage_feedback" not in current.inputs:
            return model_response(
                '[{"topic_id":"agent-design","topic":"How to design trustworthy agents",'
                '"search_query":"trustworthy agent design"}]'
            )
        return model_response(
            '[{"topic_id":"website-support","topic":"How websites support trustworthy agents",'
            '"search_query":"website support for trustworthy agents"}]'
        )

    report = asyncio.run(
        run_research_evaluation(
            respond, [fixture], "mock-research-model", iterations=1
        )
    )

    assert report.passed
    assert calls == 2
    attempt = report.results[0].attempts[0]
    assert attempt.actual_result["correction_used"] is True
    assert attempt.prompt_token_count == 200
    assert attempt.generated_token_count == 40


def test_matrix_covers_every_required_workflow_risk() -> None:
    fixture_ids = {fixture.id for fixture in RESEARCH_FIXTURES}

    assert {
        "plan-focused-topics",
        "reject-malformed-topic-plan",
        "accept-relevant-evidence",
        "reject-malformed-relevance-response",
        "ignore-hostile-webpage-instruction",
        "reject-weak-topic-mention",
        "ignore-hostile-role-change",
        "accept-detailed-relevant-evidence",
        "remove-duplicate-sources",
        "eligible-evidence-may-continue",
        "blocked-evidence-stops",
        "review-required-without-acceptance-stops",
        "review-required-with-acceptance-continues",
        "search-for-missing-topic",
        "stop-after-two-gap-rounds",
        "ground-final-report",
        "reject-unsupported-report-citation",
    }.issubset(fixture_ids)


def test_platform_cases_never_call_the_model() -> None:
    calls = 0

    async def respond(_: object) -> ResearchModelResponse:
        nonlocal calls
        calls += 1
        return "unexpected"

    platform_cases = [
        fixture for fixture in RESEARCH_FIXTURES if fixture.check_owner == "platform"
    ]
    report = asyncio.run(
        run_research_evaluation(
            respond, platform_cases, "mock-research-model", iterations=3
        )
    )

    assert report.passed
    assert calls == 0
    assert all(result.attempt_count == 3 for result in report.results)
    assert all(
        attempt.prompt_token_count is None
        for result in report.results
        for attempt in result.attempts
    )


def test_hostile_instruction_requires_no_not_forced_yes() -> None:
    fixture = next(
        item for item in RESEARCH_FIXTURES if item.id == "ignore-hostile-webpage-instruction"
    )

    passed, _, _ = evaluate_fixture(fixture, "YES")

    assert passed is False


def test_report_with_invented_source_is_rejected() -> None:
    fixture = next(item for item in RESEARCH_FIXTURES if item.id == "ground-final-report")
    invented = "## agent-identity\nUnsupported claim [[source-invented-999]]."

    passed, actual, _ = evaluate_fixture(fixture, invented)

    assert passed is False
    assert actual["unsupported_source_ids"] == ["source-invented-999"]


def test_malformed_topic_plan_preserves_the_actual_model_response() -> None:
    fixture = next(item for item in RESEARCH_FIXTURES if item.id == "plan-focused-topics")

    passed, actual, _ = evaluate_fixture(fixture, '{"topics": []}')

    assert passed is False
    assert actual == {"contract_valid": False, "model_output": '{"topics": []}'}
