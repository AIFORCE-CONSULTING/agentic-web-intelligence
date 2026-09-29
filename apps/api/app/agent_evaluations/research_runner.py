"""Offline evaluator for the complete bounded agentic research workflow."""

import json
import re
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

from ollama import AsyncClient, RequestError, ResponseError

from app.agent_evaluations.research_contracts import (
    ResearchEvaluationAttempt,
    ResearchEvaluationFixture,
    ResearchEvaluationReport,
    ResearchFixtureResult,
)
from app.agent_evaluations.research_fixtures import (
    RESEARCH_FIXTURE_VERSION,
    RESEARCH_SUITE_VERSION,
)
from app.agentic_research.contracts import TopicPlan, TopicPlanValidationError, parse_topic_plan
from app.agentic_research.planning import (
    TOPIC_PLANNING_PROMPT_VERSION,
    topic_planning_messages,
)
from app.agentic_research.relevance import (
    TOPIC_RELEVANCE_PROMPT_VERSION,
    TOPIC_RELEVANCE_SYSTEM_PROMPT,
)

GAP_SEARCH_PROMPT_VERSION = "agentic-research-gap-search-v1"
FINAL_REPORT_PROMPT_VERSION = "agentic-research-final-report-v1"
MAX_EVALUATION_ARTIFACT_CHARACTERS = 8_000
RESEARCH_SETTINGS_VERSION = "agentic-research-model-settings-v3"
SOURCE_CITATION = re.compile(r"\[\[([a-zA-Z0-9._:-]+)\]\]")

THINKING_BY_STAGE = {
    "topic_planning": True,
    "topic_relevance": True,
    "missing_topic_search": True,
    "final_report": True,
}

PROMPT_VERSIONS = {
    "topic_planning": TOPIC_PLANNING_PROMPT_VERSION,
    "topic_relevance": TOPIC_RELEVANCE_PROMPT_VERSION,
    "missing_topic_search": GAP_SEARCH_PROMPT_VERSION,
    "final_report": FINAL_REPORT_PROMPT_VERSION,
}


@dataclass(frozen=True)
class ResearchModelResponse:
    content: str
    thinking: str
    prompt_token_count: int | None
    generated_token_count: int | None
    total_duration_ns: int | None
    load_duration_ns: int | None
    prompt_duration_ns: int | None
    generation_duration_ns: int | None


@dataclass(frozen=True)
class ResearchModelIdentity:
    digest: str | None = None
    size_bytes: int | None = None
    ollama_version: str | None = None


ModelResponse = Callable[[ResearchEvaluationFixture], Awaitable[ResearchModelResponse]]


class ResearchEvaluationModelError(RuntimeError):
    """Raised when the local model cannot complete one offline decision."""


class OllamaResearchEvaluationModel:
    """Use Ollama for semantic decisions while keeping all tools unavailable."""

    def __init__(self, endpoint_url: str, model_name: str) -> None:
        self._client = AsyncClient(host=endpoint_url.rstrip("/"), timeout=120)
        self._model_name = model_name

    async def identity(self) -> ResearchModelIdentity:
        """Read the installed model identity from Ollama's public model list."""

        try:
            listing = await self._client.list()
        except (RequestError, ResponseError, OSError) as error:
            raise ResearchEvaluationModelError(
                "Ollama could not provide the installed model identity."
            ) from error
        installed = next(
            (item for item in listing.models if item.model == self._model_name),
            None,
        )
        return ResearchModelIdentity(
            digest=installed.digest if installed else None,
            size_bytes=installed.size if installed else None,
        )

    async def respond(self, fixture: ResearchEvaluationFixture) -> ResearchModelResponse:
        messages, response_format = _messages_for(fixture)
        thinking_enabled = THINKING_BY_STAGE[fixture.stage]
        request: dict[str, object] = {
            "model": self._model_name,
            "messages": messages,
            "think": thinking_enabled,
            "options": {"temperature": 0.0, "seed": 7},
        }
        if response_format is not None:
            request["format"] = response_format
        try:
            response = await self._client.chat(**request)
            return ResearchModelResponse(
                content=response.message.content or "",
                thinking=response.message.thinking or "",
                prompt_token_count=response.prompt_eval_count,
                generated_token_count=response.eval_count,
                total_duration_ns=response.total_duration,
                load_duration_ns=response.load_duration,
                prompt_duration_ns=response.prompt_eval_duration,
                generation_duration_ns=response.eval_duration,
            )
        except (RequestError, ResponseError, OSError) as error:
            raise ResearchEvaluationModelError(
                "The local model could not complete this offline evaluation case."
            ) from error


def _messages_for(
    fixture: ResearchEvaluationFixture,
) -> tuple[list[dict[str, str]], str | dict[str, object] | None]:
    if fixture.stage == "topic_planning":
        messages = topic_planning_messages(str(fixture.inputs["question"]))
        previous = fixture.inputs.get("previous_model_output")
        missing = fixture.inputs.get("coverage_feedback")
        if isinstance(previous, str) and isinstance(missing, list):
            messages.extend(
                [
                    {"role": "assistant", "content": previous},
                    {
                        "role": "user",
                        "content": (
                            "The plan did not preserve these required concepts from the "
                            f"operator's question: {', '.join(str(item) for item in missing)}. "
                            "Return a complete replacement plan that explicitly covers them."
                        ),
                    },
                ]
            )
        return messages, TopicPlan.model_json_schema()
    if fixture.stage == "topic_relevance":
        instruction = TOPIC_RELEVANCE_SYSTEM_PROMPT
    elif fixture.stage == "missing_topic_search":
        instruction = (
            "Propose one targeted web-search query for the missing research topic. "
            "Use the topic description and avoid every previous query. Return only the "
            "query, with no label, explanation, quotation marks, or Markdown."
        )
    elif fixture.stage == "final_report":
        instruction = (
            "Write a concise Markdown research report using only the supplied source "
            "summaries. Address every topic by including its topic_id as a heading or label. "
            "Cite supporting statements as [[source_id]]. Use only supplied source IDs. "
            "Clearly identify a topic when evidence is insufficient. Do not invent facts, "
            "sources, or citations. Return only the Markdown report."
        )
    else:
        raise ValueError(f"Stage {fixture.stage} does not require a model response.")
    user_content: object = fixture.inputs
    if fixture.stage == "topic_relevance":
        user_content = {
            "trusted_research_context": {
                "operator_question": fixture.inputs["question"],
                "topic": fixture.inputs["topic"],
                "source_url": fixture.inputs["source_url"],
            },
            "untrusted_webpage_excerpt": fixture.inputs["excerpt"],
        }
    return [
        {"role": "system", "content": instruction},
        {"role": "user", "content": json.dumps(user_content, ensure_ascii=True)},
    ], None


async def run_research_evaluation(
    respond: ModelResponse,
    fixtures: Sequence[ResearchEvaluationFixture],
    model_name: str,
    iterations: int,
    model_identity: ResearchModelIdentity | None = None,
) -> ResearchEvaluationReport:
    """Run every case repeatedly without calling live platform services."""

    if iterations < 1:
        raise ValueError("Evaluation iterations must be at least one.")
    started_at = datetime.now(UTC)
    results: list[ResearchFixtureResult] = []
    for fixture in fixtures:
        attempts: list[ResearchEvaluationAttempt] = []
        for attempt_number in range(1, iterations + 1):
            started = perf_counter()
            model_result: ResearchModelResponse | None = None
            try:
                if fixture.check_owner == "model":
                    model_result = await respond(fixture)
                    model_output = model_result.content
                else:
                    model_output = str(fixture.inputs.get("model_output", ""))
                passed, actual, detail = evaluate_fixture(fixture, model_output)
                if (
                    fixture.stage == "topic_planning"
                    and fixture.check_owner == "model"
                    and not passed
                    and actual.get("contract_valid") is True
                ):
                    initial_output = model_output
                    missing_terms = actual.get("missing_required_terms", [])
                    corrected_fixture = fixture.model_copy(
                        update={
                            "inputs": {
                                **fixture.inputs,
                                "previous_model_output": model_output,
                                "coverage_feedback": missing_terms,
                            }
                        }
                    )
                    correction = await respond(corrected_fixture)
                    model_result = _combined_model_response(model_result, correction)
                    passed, actual, detail = evaluate_fixture(
                        fixture, correction.content
                    )
                    actual["correction_used"] = True
                    actual["initial_model_output"] = initial_output
                    actual["initial_missing_required_terms"] = missing_terms
                    actual["corrected_model_output"] = correction.content
                elif fixture.stage == "topic_planning" and fixture.check_owner == "model":
                    actual["correction_used"] = False
            except ResearchEvaluationModelError as error:
                passed, actual, detail = False, {"model_error": True}, str(error)
            attempts.append(
                ResearchEvaluationAttempt(
                    fixture_id=fixture.id,
                    attempt_number=attempt_number,
                    stage=fixture.stage,
                    check_owner=fixture.check_owner,
                    prompt_version=PROMPT_VERSIONS.get(fixture.stage),
                    thinking_enabled=(
                        THINKING_BY_STAGE[fixture.stage]
                        if fixture.check_owner == "model"
                        else None
                    ),
                    passed=passed,
                    expected_result=fixture.expected,
                    actual_result=_bounded_artifact(actual),
                    validator_detail=detail,
                    duration_ms=round((perf_counter() - started) * 1000),
                    prompt_token_count=(
                        model_result.prompt_token_count if model_result else None
                    ),
                    generated_token_count=(
                        model_result.generated_token_count if model_result else None
                    ),
                    thinking_character_count=(
                        len(model_result.thinking) if model_result else None
                    ),
                    ollama_total_duration_ns=(
                        model_result.total_duration_ns if model_result else None
                    ),
                    ollama_load_duration_ns=(
                        model_result.load_duration_ns if model_result else None
                    ),
                    ollama_prompt_duration_ns=(
                        model_result.prompt_duration_ns if model_result else None
                    ),
                    ollama_generation_duration_ns=(
                        model_result.generation_duration_ns if model_result else None
                    ),
                )
            )
        results.append(
            ResearchFixtureResult(
                fixture_id=fixture.id,
                stage=fixture.stage,
                check_owner=fixture.check_owner,
                passed=all(attempt.passed for attempt in attempts),
                passed_attempt_count=sum(attempt.passed for attempt in attempts),
                attempt_count=len(attempts),
                attempts=attempts,
            )
        )
    identity = model_identity or ResearchModelIdentity()
    return ResearchEvaluationReport(
        suite_version=RESEARCH_SUITE_VERSION,
        fixture_version=RESEARCH_FIXTURE_VERSION,
        model_name=model_name,
        model_digest=identity.digest,
        model_size_bytes=identity.size_bytes,
        ollama_version=identity.ollama_version,
        prompt_versions=PROMPT_VERSIONS,
        settings_version=RESEARCH_SETTINGS_VERSION,
        iterations=iterations,
        started_at=started_at,
        completed_at=datetime.now(UTC),
        passed_case_count=sum(result.passed for result in results),
        case_count=len(results),
        results=results,
    )


def evaluate_fixture(
    fixture: ResearchEvaluationFixture, model_output: str
) -> tuple[bool, dict[str, object], str]:
    """Apply the real response contracts and fixed platform rules to one case."""

    if fixture.stage == "topic_planning":
        return _evaluate_topic_plan(fixture, model_output)
    if fixture.stage == "topic_relevance":
        return _evaluate_relevance(fixture, model_output)
    if fixture.stage == "source_deduplication":
        known = set(_strings(fixture.inputs["known_urls"]))
        new_urls = [url for url in _strings(fixture.inputs["returned_urls"]) if url not in known]
        actual = {"new_urls": new_urls}
    elif fixture.stage == "trust_policy":
        disposition = str(fixture.inputs["disposition"])
        accepted = bool(fixture.inputs["human_acceptance"])
        actual = {
            "may_continue": disposition in {"eligible", "eligible_with_notice"}
            or (disposition == "review_required" and accepted)
        }
    elif fixture.stage == "missing_topic_search":
        query = model_output
        previous = {item.casefold() for item in _strings(fixture.inputs["previous_queries"])}
        required = _strings(fixture.expected["required_terms"])
        valid = (
            query == query.strip()
            and "\n" not in query
            and 3 <= len(query) <= 512
            and query.casefold() not in previous
            and all(term.casefold() in query.casefold() for term in required)
        )
        actual = {"valid": valid, "query": query}
        return valid, actual, "Targeted query satisfied the contract." if valid else (
            "Targeted query was repeated, malformed, or did not address the missing topic."
        )
    elif fixture.stage == "loop_limit":
        actual = {"another_round_allowed": int(fixture.inputs["completed_gap_rounds"]) < 2}
    elif fixture.stage == "final_report":
        return _evaluate_report(fixture, model_output)
    else:
        raise ValueError(f"Unsupported evaluation stage: {fixture.stage}")
    passed = actual == fixture.expected
    return passed, actual, "Platform rule matched the expected result." if passed else (
        "Platform rule did not match the expected result."
    )


def _evaluate_topic_plan(
    fixture: ResearchEvaluationFixture, model_output: str
) -> tuple[bool, dict[str, object], str]:
    try:
        plan = parse_topic_plan(model_output)
        combined = " ".join(
            f"{topic.topic} {topic.search_query}" for topic in plan.root
        ).casefold()
        required = _strings(fixture.expected.get("required_terms", []))
        valid = all(term.casefold() in combined for term in required)
        actual = {
            "contract_valid": True,
            "topic_count": len(plan.root),
            "model_output": model_output,
        }
        if required:
            actual["required_terms_present"] = valid
            actual["missing_required_terms"] = [
                term for term in required if term.casefold() not in combined
            ]
            return (
                valid,
                actual,
                "Topic plan was valid and covered the required concepts."
                if valid
                else "Topic plan was valid JSON but omitted a required concept.",
            )
        expected_valid = bool(fixture.expected["contract_valid"])
        return expected_valid, actual, "Topic-plan contract result matched."
    except TopicPlanValidationError:
        actual = {"contract_valid": False, "model_output": model_output}
        passed = fixture.expected.get("contract_valid") is False
        return passed, actual, "Malformed topic plan was rejected." if passed else (
            "The model did not return a valid topic plan."
        )


def _evaluate_relevance(
    fixture: ResearchEvaluationFixture, model_output: str
) -> tuple[bool, dict[str, object], str]:
    if model_output == "YES":
        decision = "relevant"
    elif model_output == "NO":
        decision = "not_relevant"
    else:
        decision = "model_failure"
    if "response" in fixture.expected:
        passed = model_output == fixture.expected["response"]
        actual = {"response": model_output, "decision": decision}
    else:
        passed = decision == fixture.expected["decision"]
        actual = {"decision": decision}
    return passed, actual, "Relevance response matched the strict contract." if passed else (
        "Relevance response did not match the expected exact decision."
    )


def _evaluate_report(
    fixture: ResearchEvaluationFixture, model_output: str
) -> tuple[bool, dict[str, object], str]:
    allowed_sources = {
        str(source["source_id"])
        for source in fixture.inputs["sources"]
        if isinstance(source, dict) and "source_id" in source
    }
    required_topics = {
        str(topic["topic_id"])
        for topic in fixture.inputs["topics"]
        if isinstance(topic, dict) and "topic_id" in topic
    }
    cited_sources = set(SOURCE_CITATION.findall(model_output))
    valid = (
        bool(model_output.strip())
        and required_topics.issubset(set(model_output.split()))
        and cited_sources.issubset(allowed_sources)
        and (not allowed_sources or bool(cited_sources))
    )
    actual = {
        "valid": valid,
        "topic_ids_present": sorted(topic for topic in required_topics if topic in model_output),
        "cited_source_ids": sorted(cited_sources),
        "unsupported_source_ids": sorted(cited_sources - allowed_sources),
        "model_output": model_output,
    }
    expected_valid = bool(fixture.expected.get("valid", True))
    passed = valid is expected_valid
    return passed, actual, "Report grounding result matched the expected outcome." if passed else (
        "Report omitted a topic, lacked a supplied citation, or cited an unsupported source."
    )


def _strings(value: object) -> list[str]:
    return [str(item) for item in value] if isinstance(value, list) else []


def _combined_model_response(
    first: ResearchModelResponse, second: ResearchModelResponse
) -> ResearchModelResponse:
    """Combine resource use for the one permitted planning correction."""

    def total(left: int | None, right: int | None) -> int | None:
        return None if left is None and right is None else (left or 0) + (right or 0)

    return ResearchModelResponse(
        content=second.content,
        thinking=f"{first.thinking}\n{second.thinking}",
        prompt_token_count=total(first.prompt_token_count, second.prompt_token_count),
        generated_token_count=total(first.generated_token_count, second.generated_token_count),
        total_duration_ns=total(first.total_duration_ns, second.total_duration_ns),
        load_duration_ns=total(first.load_duration_ns, second.load_duration_ns),
        prompt_duration_ns=total(first.prompt_duration_ns, second.prompt_duration_ns),
        generation_duration_ns=total(
            first.generation_duration_ns, second.generation_duration_ns
        ),
    )


def _bounded_artifact(actual: dict[str, object]) -> dict[str, object]:
    serialized = json.dumps(actual, ensure_ascii=True)
    if len(serialized) <= MAX_EVALUATION_ARTIFACT_CHARACTERS:
        return actual
    return {"truncated": True, "preview": serialized[:MAX_EVALUATION_ARTIFACT_CHARACTERS]}


def write_research_report(report: ResearchEvaluationReport, output_path: Path) -> None:
    """Write the sanitized offline report beneath the caller-selected artifact path."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report.model_dump_json(indent=2), encoding="ascii")
