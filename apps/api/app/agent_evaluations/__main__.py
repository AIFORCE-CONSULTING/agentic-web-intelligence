"""Run fixed local-agent tool-use fixtures against a local Ollama model."""

import argparse
import asyncio
from datetime import UTC, datetime
from pathlib import Path

from app.agent_evaluations.fixtures import COOKIE_PREFERENCE_TOOL, FIXTURE_VERSION, FIXTURES
from app.agent_evaluations.research_fixtures import RESEARCH_FIXTURES
from app.agent_evaluations.research_runner import (
    OllamaResearchEvaluationModel,
    run_research_evaluation,
    write_research_report,
)
from app.agent_evaluations.runner import (
    OllamaProposalModel,
    run_evaluation,
    run_sync,
    write_report,
)
from app.local_models.service import LocalModelProviderService


async def _run_research_suite(
    model: OllamaResearchEvaluationModel, model_name: str, iterations: int
):
    identity = await model.identity()
    return await run_research_evaluation(
        model.respond,
        RESEARCH_FIXTURES,
        model_name,
        iterations,
        identity,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", default="http://localhost:11434")
    parser.add_argument("--model", default="qwen3:1.7b")
    parser.add_argument("--iterations", default=5, type=int)
    parser.add_argument("--suite", choices=("cookie", "research"), default="cookie")
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()

    endpoint = LocalModelProviderService.validate_endpoint(arguments.endpoint)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    default_output = Path("artifacts/agent-evaluations") / (
        f"{arguments.model}-{arguments.suite}-{timestamp}.json"
    )
    output = arguments.output or default_output
    if arguments.iterations < 1:
        parser.error("--iterations must be at least 1")
    if arguments.suite == "research":
        model = OllamaResearchEvaluationModel(endpoint, arguments.model)
        report = asyncio.run(
            _run_research_suite(model, arguments.model, arguments.iterations)
        )
        write_research_report(report, output)
        print(
            "Offline research-workflow evaluation: "
            f"{report.passed_case_count}/{report.case_count} cases passed across "
            f"{report.iterations} attempts each. "
            f"Report: {output}"
        )
        return

    model = OllamaProposalModel(endpoint, arguments.model, COOKIE_PREFERENCE_TOOL)
    report = run_sync(
        run_evaluation(
            model.propose,
            FIXTURES,
            FIXTURE_VERSION,
            arguments.model,
            arguments.iterations,
        )
    )
    write_report(report, output)
    print(
        "Local agent evaluation: "
        f"{report.passed_fixture_count}/{report.fixture_count} fixtures passed across "
        f"{report.iterations} attempts each. "
        f"Report: {output}"
    )


if __name__ == "__main__":
    main()
