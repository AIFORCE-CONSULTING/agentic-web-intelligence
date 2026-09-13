from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CreateEvidenceSummaryExecutionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_id: UUID
    urls: list[str] = Field(min_length=1, max_length=5)
    rerun_existing: bool = False


class EvidenceSummaryExecutionSource(BaseModel):
    url: str
    status: Literal[
        "pending", "extracting", "extracted", "summarizing", "completed", "failed", "cancelled"
    ] = "pending"
    content_hash: str | None = None
    chunk_count: int | None = None
    summary: str | None = None
    keywords: list[str] | None = None
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
    created_at: datetime
    updated_at: datetime
    sources: list[EvidenceSummaryExecutionSource]
