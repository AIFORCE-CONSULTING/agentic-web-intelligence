"""Strict model-output contracts for agentic research planning."""

import json
from datetime import datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, RootModel, ValidationError, model_validator

MAX_RESEARCH_TOPICS = 3


class ResearchTopic(BaseModel):
    """One focused area of the operator's research question."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    topic_id: str = Field(
        min_length=3,
        max_length=64,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )
    topic: str = Field(min_length=10, max_length=512)
    search_query: str = Field(min_length=3, max_length=512)


TopicList = Annotated[list[ResearchTopic], Field(min_length=1, max_length=MAX_RESEARCH_TOPICS)]


class TopicPlan(RootModel[TopicList]):
    """A bounded JSON array of focused topics proposed for one research question."""

    @model_validator(mode="after")
    def require_unique_topic_ids(self) -> Self:
        topic_ids = [item.topic_id for item in self.root]
        if len(topic_ids) != len(set(topic_ids)):
            raise ValueError("Every topic_id must be unique within the research plan.")
        return self


class TopicPlanValidationError(ValueError):
    """Raised when model output cannot become a trusted topic plan."""


def parse_topic_plan(content: str) -> TopicPlan:
    """Validate raw model text as the exact JSON-array topic contract."""

    try:
        decoded = json.loads(content)
        return TopicPlan.model_validate(decoded)
    except (json.JSONDecodeError, ValidationError) as error:
        raise TopicPlanValidationError(
            "The local model returned an invalid topic-planning response."
        ) from error


RelevanceDecision = Literal["relevant", "not_relevant", "model_failure"]
CoverageRequirement = Literal["evidence", "trust", "relevance", "summary"]


class TopicRelevanceRecord(BaseModel):
    """One topic-specific model decision for an exact evidence version."""

    id: UUID
    topic_record_id: UUID
    source_url: str
    content_hash: str
    decision: RelevanceDecision
    model_name: str
    prompt_version: str
    created_at: datetime


class TopicCoverageFacts(BaseModel):
    """Canonical platform records required before evidence supports a topic."""

    topic_record_id: UUID | None = None
    evidence_id: UUID | None = None
    trust_evaluation_id: UUID | None = None
    relevance_decision_id: UUID | None = None
    summary_artifact_id: UUID | None = None


class TopicCoverageAssessment(BaseModel):
    """Explain whether one evidence version currently contributes to a topic."""

    counts_toward_topic: bool
    missing_requirements: list[CoverageRequirement]


class TopicCoverageEvidence(BaseModel):
    """One fully qualified evidence version stored against a planned topic."""

    source_url: str
    content_hash: str
    evidence_id: UUID
    trust_evaluation_id: UUID
    relevance_decision_id: UUID
    summary_artifact_id: UUID
    qualified_at: datetime


class TopicCoverage(BaseModel):
    """Stored coverage for one planned topic, independent of source keywords."""

    topic_id: str
    topic: str
    search_query: str
    status: Literal["uncovered", "covered"]
    evidence: list[TopicCoverageEvidence] = Field(default_factory=list)


def assess_topic_coverage(facts: TopicCoverageFacts) -> TopicCoverageAssessment:
    """Apply the fixed four-record rule without model interpretation."""

    requirements: tuple[tuple[CoverageRequirement, UUID | None], ...] = (
        ("evidence", facts.evidence_id),
        ("trust", facts.trust_evaluation_id),
        ("relevance", facts.relevance_decision_id),
        ("summary", facts.summary_artifact_id),
    )
    missing = [name for name, record_id in requirements if record_id is None]
    return TopicCoverageAssessment(
        counts_toward_topic=facts.topic_record_id is not None and not missing,
        missing_requirements=missing,
    )
