from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CreateEvidenceSummaryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_id: UUID
    content_hashes: list[str] = Field(min_length=1, max_length=5)


class EvidenceSummarySource(BaseModel):
    content_hash: str
    url: str
    chunk_count: int
    status: Literal["pending"] = "pending"


class EvidenceSummaryBatch(BaseModel):
    id: UUID
    workspace_id: UUID
    run_id: UUID
    route: Literal["direct", "durable"]
    status: Literal["pending"] = "pending"
    created_at: datetime
    sources: list[EvidenceSummarySource]
