"""Stable contracts between agent workflows and governed web tools."""

from datetime import datetime

from pydantic import BaseModel, Field


class ExtractRequest(BaseModel):
    """A request for text evidence from one public webpage."""

    url: str = Field(min_length=1, max_length=2_048)


class Evidence(BaseModel):
    """Normalized, bounded evidence returned from the web boundary."""

    url: str
    retrieved_at: datetime
    content_type: str
    text: str = Field(min_length=1)
    content_hash: str
    extraction_method: str


class ToolPolicyError(ValueError):
    """Raised when a request is outside the read-only web-tool policy."""
