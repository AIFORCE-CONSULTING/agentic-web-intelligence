"""Stable contracts between agent workflows and governed web tools."""

from datetime import datetime

from pydantic import BaseModel, Field


class ExtractRequest(BaseModel):
    """A request for text evidence from one public webpage."""

    url: str = Field(min_length=1, max_length=2_048)


class SearchRequest(BaseModel):
    """A bounded query for approved public-web discovery."""

    query: str = Field(min_length=1, max_length=512)
    max_results: int = Field(default=5, ge=1, le=10)


class SearchResult(BaseModel):
    """Normalized candidate source returned by the search provider."""

    title: str = Field(min_length=1, max_length=512)
    url: str
    snippet: str = Field(default="", max_length=2_000)
    engine: str | None = Field(default=None, max_length=128)


class SearchResponse(BaseModel):
    """Search evidence before a workflow selects a page to extract."""

    query: str
    results: list[SearchResult]


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


class ToolProviderError(RuntimeError):
    """Raised when a configured web-tool provider cannot complete a request."""
