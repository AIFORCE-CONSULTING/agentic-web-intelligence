from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CreateEvidenceSummaryExecutionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_id: UUID
    urls: list[str] = Field(min_length=1, max_length=5)


class RegenerateEvidenceSummaryRequest(BaseModel):
    """An explicit operator request to refresh the existing selected summary artifacts."""

    model_config = ConfigDict(extra="forbid")
    urls: list[str] = Field(min_length=1, max_length=5)


class EvidenceSummaryExecutionSource(BaseModel):
    url: str
    status: Literal[
        "pending", "extracting", "extracted", "summarizing", "completed", "failed", "cancelled"
    ] = "pending"
    content_hash: str | None = None
    content_characters: int | None = None
    chunk_count: int | None = None
    chunking_policy_version: str | None = None
    summary: str | None = None
    keywords: list[str] | None = None
    keyword_coverage: dict[str, str] | None = None
    prompt_version: str | None = None
    evidence_sufficient: bool | None = None
    artifact_reused: bool = False
    failure_reason: str | None = None
    failure_category: str | None = None
    summary_attempt_count: int = 0
    model_version: str | None = None


class EvidenceSummaryExecution(BaseModel):
    id: UUID
    workspace_id: UUID
    run_id: UUID
    route: Literal["undetermined", "direct", "durable"] = "undetermined"
    status: Literal[
        "pending",
        "extracting",
        "awaiting_execution",
        "summarizing",
        "completed",
        "failed",
        "cancelled",
    ] = "pending"
    regeneration_attempt: int = 0
    regeneration_requested: bool = False
    created_at: datetime
    updated_at: datetime
    sources: list[EvidenceSummaryExecutionSource]


class EvidenceSummaryWorkSet(BaseModel):
    """Combined outcome for all internal summary jobs of one research task."""

    id: UUID
    workspace_id: UUID
    run_id: UUID
    status: Literal["created", "waiting", "completed", "failed"]
    execution_ids: list[UUID] = Field(default_factory=list)


class WorkspaceEvidenceSummaryArtifact(BaseModel):
    """One newest stored source summary for a canonical URL in a workspace."""

    run_id: UUID
    url: str
    title: str
    chunk_count: int | None = None
    summary: str
    keywords: list[str]
    keyword_coverage: dict[str, str] | None = None
    prompt_version: str | None = None
    evidence_sufficient: bool


class WorkspaceEvidenceSummaryArtifactList(BaseModel):
    artifacts: list[WorkspaceEvidenceSummaryArtifact]
