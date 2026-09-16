"""Safe contracts for the local Ollama provider boundary."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class LocalModelProviderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    endpoint_url: str = Field(min_length=1, max_length=256)
    model_name: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")


class LocalModelProviderConfiguration(LocalModelProviderRequest):
    workspace_id: UUID
    updated_at: datetime


class LocalModelProviderReadiness(BaseModel):
    mode: Literal["unconfigured", "ready", "unavailable", "invalid"]
    provider: Literal["ollama"] = "ollama"
    endpoint_url: str | None = None
    model_name: str | None = None
    detail: str
