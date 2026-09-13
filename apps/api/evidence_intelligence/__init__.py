"""Pure evidence-processing contracts, deliberately independent of the platform."""

from evidence_intelligence.chunking import EvidenceChunk, chunk_text
from evidence_intelligence.contracts import PreparedBatch, PreparedSource, SourceInput
from evidence_intelligence.preparation import prepare_batch
from evidence_intelligence.routing import ExecutionRoute, route_request

__all__ = [
    "EvidenceChunk", "ExecutionRoute", "PreparedBatch", "PreparedSource", "SourceInput",
    "chunk_text", "prepare_batch", "route_request",
]
