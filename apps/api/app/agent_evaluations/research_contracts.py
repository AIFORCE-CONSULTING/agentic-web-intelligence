"""Contracts for the complete offline agentic research evaluation."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ResearchEvaluationStage = Literal[
    "topic_planning",
    "topic_relevance",
    "source_deduplication",
    "trust_policy",
    "missing_topic_search",
    "loop_limit",
    "final_report",
]
ResearchCheckOwner = Literal["model", "platform"]


class ResearchEvaluationFixture(BaseModel):
    """One readable, versioned case in the research-workflow test matrix."""

    model_config = ConfigDict(extra="forbid")

    id: str
    stage: ResearchEvaluationStage
    check_owner: ResearchCheckOwner
    description: str
    inputs: dict[str, object]
    expected: dict[str, object]


class ResearchEvaluationAttempt(BaseModel):
    """One result with enough detail to understand a failure."""

    fixture_id: str
    attempt_number: int = Field(ge=1)
    stage: ResearchEvaluationStage
    check_owner: ResearchCheckOwner
    prompt_version: str | None = None
    thinking_enabled: bool | None = None
    passed: bool
    expected_result: dict[str, object]
    actual_result: dict[str, object]
    validator_detail: str
    duration_ms: int = Field(ge=0)
    prompt_token_count: int | None = Field(default=None, ge=0)
    generated_token_count: int | None = Field(default=None, ge=0)
    thinking_character_count: int | None = Field(default=None, ge=0)
    ollama_total_duration_ns: int | None = Field(default=None, ge=0)
    ollama_load_duration_ns: int | None = Field(default=None, ge=0)
    ollama_prompt_duration_ns: int | None = Field(default=None, ge=0)
    ollama_generation_duration_ns: int | None = Field(default=None, ge=0)


class ResearchFixtureResult(BaseModel):
    """Consistency result across repeated attempts of one case."""

    fixture_id: str
    stage: ResearchEvaluationStage
    check_owner: ResearchCheckOwner
    passed: bool
    passed_attempt_count: int = Field(ge=0)
    attempt_count: int = Field(ge=1)
    attempts: list[ResearchEvaluationAttempt]


class ResearchEvaluationReport(BaseModel):
    """Offline evidence about a model and the fixed platform controls around it."""

    suite_version: str
    fixture_version: str
    model_name: str
    model_digest: str | None = None
    model_size_bytes: int | None = Field(default=None, ge=0)
    ollama_version: str | None = None
    prompt_versions: dict[str, str]
    settings_version: str
    iterations: int = Field(ge=1)
    started_at: datetime
    completed_at: datetime
    passed_case_count: int = Field(ge=0)
    case_count: int = Field(ge=1)
    results: list[ResearchFixtureResult]

    @property
    def passed(self) -> bool:
        return self.passed_case_count == self.case_count
