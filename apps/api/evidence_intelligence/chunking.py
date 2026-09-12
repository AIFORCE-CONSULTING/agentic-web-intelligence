"""Pure, deterministic text chunking with transparent coverage metadata."""

from dataclasses import dataclass

CHUNK_CHARACTERS = 6_000
OVERLAP_CHARACTERS = 500


@dataclass(frozen=True)
class EvidenceChunk:
    index: int
    text: str
    start_offset: int
    end_offset: int


def chunk_text(text: str) -> list[EvidenceChunk]:
    """Cover non-empty text with overlapping character chunks and no platform dependencies."""

    if not text.strip():
        raise ValueError("Evidence text must not be empty.")
    chunks: list[EvidenceChunk] = []
    start = 0
    while start < len(text):
        end = min(start + CHUNK_CHARACTERS, len(text))
        chunks.append(EvidenceChunk(len(chunks), text[start:end], start, end))
        if end == len(text):
            break
        start = end - OVERLAP_CHARACTERS
    return chunks
