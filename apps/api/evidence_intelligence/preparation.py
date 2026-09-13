"""Prepare one-to-five source inputs without invoking a provider or platform service."""

from evidence_intelligence.chunking import chunk_text
from evidence_intelligence.contracts import PreparedBatch, PreparedSource, SourceInput


def prepare_batch(sources: list[SourceInput]) -> PreparedBatch:
    """Create transparent chunks for every requested source; never skip one."""

    if not 1 <= len(sources) <= 5:
        raise ValueError("A summary request must contain from one to five sources.")
    prepared = tuple(
        PreparedSource(
            source_id=source.source_id,
            source_url=source.source_url,
            content_hash=source.content_hash,
            chunks=tuple(chunk_text(source.text)),
        )
        for source in sources
    )
    return PreparedBatch(prepared, sum(len(source.chunks) for source in prepared))
