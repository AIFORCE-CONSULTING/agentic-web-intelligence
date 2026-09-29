"""Typed contracts for the offline public cookie-preference evaluation."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ToolContract(BaseModel):
    """One real MCP tool definition visible to the model during evaluation."""

    model_config = ConfigDict(extra="forbid")

    name: str
    description: str
    input_schema: dict[str, object]


class ToolProposal(BaseModel):
    """A native MCP tool request returned by the model."""

    model_config = ConfigDict(extra="forbid")

    tool_name: str
    arguments: dict[str, object]


class EvaluationFixture(BaseModel):
    """One valid, agent-ready public cookie-preference task."""

    model_config = ConfigDict(extra="forbid")

    id: str
    task: str
    source_id: str = Field(min_length=1)
    webpage_text: str
    expected: ToolProposal


class FixtureAttempt(BaseModel):
    """One deterministic attempt for a public cookie-preference task."""

    passed: bool
    proposal: ToolProposal | None = None
    validator_detail: str
    duration_ms: int = Field(ge=0)


class FixtureResult(BaseModel):
    """Consistency result for one public cookie-preference task."""

    fixture_id: str
    passed: bool
    passed_attempt_count: int = Field(ge=0)
    attempt_count: int = Field(ge=1)
    attempts: list[FixtureAttempt]


class EvaluationReport(BaseModel):
    """A local artifact that informs, but never grants, model authority."""

    fixture_version: str
    model_name: str
    started_at: datetime
    completed_at: datetime
    passed_fixture_count: int = Field(ge=0)
    fixture_count: int = Field(ge=0)
    iterations: int = Field(ge=1)
    results: list[FixtureResult]

    @property
    def passed(self) -> bool:
        return self.passed_fixture_count == self.fixture_count
