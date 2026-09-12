"""Pure evidence-processing contracts, deliberately independent of the platform."""

from evidence_intelligence.chunking import EvidenceChunk, chunk_text
from evidence_intelligence.routing import ExecutionRoute, route_request

__all__ = ["EvidenceChunk", "ExecutionRoute", "chunk_text", "route_request"]
