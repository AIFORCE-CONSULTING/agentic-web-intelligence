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
    evidence_sufficient: bool | None = None
    artifact_reused: bool = False
    failure_reason: str | None = None


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
