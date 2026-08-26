"""Stable contracts between agent workflows and governed web tools."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class ExtractRequest(BaseModel):
    """A request for text evidence from one public webpage."""

    url: str = Field(min_length=1, max_length=2_048)


class BatchExtractRequest(BaseModel):
    """A bounded, ordered selection of discovered sources to extract."""

    urls: list[str] = Field(min_length=1, max_length=10)


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


class BatchExtractionOutcome(BaseModel):
    """The durable outcome of one source in a sequential batch."""

    url: str
    status: Literal["succeeded", "failed", "denied"]
    evidence: Evidence | None = None
    reason: str | None = None
    upstream_status: int | None = None


class BatchExtractResponse(BaseModel):
    """A completed batch with an outcome for every requested source."""

    run_id: UUID
    outcomes: list[BatchExtractionOutcome]


class ResearchRunRequest(BaseModel):
    """Create a durable, discovery-first research run."""

    question: str = Field(min_length=1, max_length=512)
    max_results: int = Field(default=5, ge=1, le=10)


class SourceCandidate(SearchResult):
    """A discovered source associated with one research run."""

    rank: int = Field(ge=1)


class AuditEvent(BaseModel):
    """An append-only event describing a run decision or outcome."""

    event_type: str
    occurred_at: datetime
    details: dict[str, object] = Field(default_factory=dict)


class ResearchRun(BaseModel):
    """Durable research record returned to operators and future agents."""

    id: UUID
    question: str
    status: str
    created_at: datetime
    updated_at: datetime
    sources: list[SourceCandidate] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    audit_events: list[AuditEvent] = Field(default_factory=list)


class ResearchRunSummary(BaseModel):
    """A bounded library entry for reopening a durable research run."""

    id: UUID
    question: str
    status: str
    created_at: datetime
    updated_at: datetime
    source_count: int = Field(ge=0)
    evidence_count: int = Field(ge=0)


class ResearchRunList(BaseModel):
    """Most recently updated runs, deliberately bounded for an operator console."""

    runs: list[ResearchRunSummary]


class ToolPolicyError(ValueError):
    """Raised when a request is outside the read-only web-tool policy."""


class ToolProviderError(RuntimeError):
    """Raised when a configured web-tool provider cannot complete a request."""


class ToolRetrievalError(ToolProviderError):
    """Raised when an approved public source cannot be retrieved safely."""

    def __init__(self, message: str, upstream_status: int | None = None) -> None:
        super().__init__(message)
        self.upstream_status = upstream_status


class ResearchStoreUnavailable(RuntimeError):
    """Raised when the durable research store is not configured or reachable."""
