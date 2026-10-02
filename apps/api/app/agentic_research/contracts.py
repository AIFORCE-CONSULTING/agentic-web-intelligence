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
    model_output: str
    failure_reason: str | None = None
    created_at: datetime


class TopicRelevanceInput(BaseModel):
    """Eligible evidence and topic context approved for one relevance prompt."""

    operator_question: str
    topic_id: str
    topic: str
    source_url: str
    content_hash: str
    evidence_text: str


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


class TopicSourceAssociation(BaseModel):
    """A stored explanation of which topic search produced a candidate URL."""

    topic_id: str
    source_url: str
    result_rank: int = Field(ge=1, le=50)


class ResearchReportSource(BaseModel):
    """One qualified stored summary supplied to final report generation."""

    topic_id: str
    topic: str
    source_url: str
    summary: str


ReportQualityGrade = Literal["PASS", "FAIL"]
ReportOrigin = Literal["model_pass", "model_fail", "fallback"]
ReportQualityReasonCode = Literal[
    "missing_topic_coverage",
    "unrepresented_qualified_source",
    "narrative_length",
    "model_unavailable",
    "model_timeout",
    "malformed_model_response",
    "malformed_topic_output",
    "unsupported_citation_label",
    "insufficient_topic_evidence",
    "unsafe_model_draft",
]
ReportAttemptStatus = Literal["started", "pass", "fail", "unusable"]
CitationFailureCode = Literal[
    "unknown_citation_label",
    "ambiguous_citation_label",
    "cross_topic_citation_label",
]
TopicSectionQualityReasonCode = Literal[
    "unsupported_citation_label",
    "malformed_topic_output",
    "model_timeout",
    "insufficient_topic_evidence",
]


class ReportQualityReason(BaseModel):
    """One concise, server-validated explanation of report quality."""

    code: ReportQualityReasonCode
    message: str = Field(min_length=1, max_length=512)


class ReportSupportingSource(BaseModel):
    """A frozen source identity that the UI maps to a stored summary."""

    source_ref: str
    topic_id: str
    title: str
    url: str


class ReportInput(BaseModel):
    """An immutable, qualified summary snapshot used to create one report."""

    topic_record_id: UUID
    topic_id: str
    topic: str
    summary_artifact_id: UUID
    source_ref: str
    source_url: str
    source_title: str
    summary_text: str
    content_hash: str
    position: int


class ReportExclusion(BaseModel):
    """A noncontributing source disclosed separately from report evidence."""

    title: str
    url: str
    topic_ids: list[str]
    reason_code: str
    reason: str


class FinalReportFinding(BaseModel):
    """One model-proposed finding tied to known, topic-scoped source references."""

    text: str = Field(min_length=1, max_length=4000)
    source_refs: list[str] = Field(min_length=1, max_length=20)


class TopicFindingDraft(BaseModel):
    """The only shape accepted from the local model for one topic section."""

    model_config = ConfigDict(extra="forbid")

    findings: list[FinalReportFinding] = Field(default_factory=list, max_length=12)


class FinalReportAttempt(BaseModel):
    """Diagnostic record for one bounded report-drafting attempt."""

    attempt_number: int = Field(ge=1, le=2)
    topic_id: str | None = None
    status: ReportAttemptStatus
    raw_response: str = ""
    validation_errors: list[str] = Field(default_factory=list)
    model_name: str | None = None
    prompt_version: str
    duration_ms: int | None = Field(default=None, ge=0)
    input_characters: int = Field(default=0, ge=0)
    failure_code: str | None = None


class ResearchReport(BaseModel):
    """The newest grounded report stored for one research run."""

    id: UUID | None = None
    run_id: UUID
    markdown: str
    model_name: str | None = None
    prompt_version: str
    contract_version: str = "legacy"
    quality_grade: ReportQualityGrade = "FAIL"
    quality_reasons: list[ReportQualityReason] = Field(default_factory=list)
    report_origin: ReportOrigin = "fallback"
    current: bool = True
    supporting_sources: list[ReportSupportingSource] = Field(default_factory=list)
    exclusions: list[ReportExclusion] = Field(default_factory=list)
    created_at: datetime


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
