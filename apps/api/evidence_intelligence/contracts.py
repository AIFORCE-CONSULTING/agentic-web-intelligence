"""Pure typed contracts for derived evidence intelligence; no platform imports."""

from dataclasses import dataclass

from evidence_intelligence.chunking import EvidenceChunk


@dataclass(frozen=True)
class SourceInput:
    source_id: str
    source_url: str
    content_hash: str
    text: str


@dataclass(frozen=True)
class PreparedSource:
    source_id: str
    source_url: str
    content_hash: str
    chunks: tuple[EvidenceChunk, ...]


@dataclass(frozen=True)
class PreparedBatch:
    sources: tuple[PreparedSource, ...]
    total_chunk_count: int
