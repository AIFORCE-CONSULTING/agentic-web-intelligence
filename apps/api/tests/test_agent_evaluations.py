"""Tests for the offline public cookie-preference evaluation harness."""

import asyncio

import pytest
from pydantic import ValidationError

from app.agent_evaluations.contracts import EvaluationFixture, ToolProposal
from app.agent_evaluations.fixtures import COOKIE_PREFERENCE_TOOL, FIXTURE_VERSION, FIXTURES
from app.agent_evaluations.runner import OllamaProposalModel, run_evaluation, validate_proposal


def test_valid_fixtures_pass_with_exact_mock_requests() -> None:
    async def propose(fixture: EvaluationFixture) -> ToolProposal:
        return fixture.expected

    report = asyncio.run(
        run_evaluation(propose, FIXTURES, FIXTURE_VERSION, "mock-local-model", iterations=3)
    )

    assert report.passed
    assert report.passed_fixture_count == len(FIXTURES)
    assert all(result.passed_attempt_count == 3 for result in report.results)


def test_missing_source_id_is_rejected_before_an_agent_task_exists() -> None:
    fixture = FIXTURES[0].model_dump()
    fixture["source_id"] = ""

    with pytest.raises(ValidationError):
        EvaluationFixture.model_validate(fixture)


def test_native_catalog_contains_only_the_real_cookie_preference_tool() -> None:
    model = OllamaProposalModel("http://localhost:11434", "fixture-model", COOKIE_PREFERENCE_TOOL)

    tools = model._native_tools()

    assert [tool["function"]["name"] for tool in tools] == ["web.resolve_public_consent"]
    assert tools[0]["function"]["parameters"]["required"] == ["source_id", "preference"]


def test_unexpected_tool_request_fails_contract_validation() -> None:
    unexpected = ToolProposal(
        tool_name="browser.click",
        arguments={"selector": "#accept-all"},
    )

    assert (
        validate_proposal(unexpected, FIXTURES[0].expected)
        == "Expected tool web.resolve_public_consent, received browser.click."
    )
