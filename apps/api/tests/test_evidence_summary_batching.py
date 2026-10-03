import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from app.evidence_summaries.contracts import EvidenceSummaryWorkSet
from app.evidence_summaries.service import (
    EvidenceSummaryAutomation,
    SummaryWorkItem,
    plan_summary_batches,
)
from app.web_research.contracts import Evidence, ResearchRun, SourceCandidate
from evidence_intelligence.chunking import CHUNK_CHARACTERS, OVERLAP_CHARACTERS


def _text_for_chunks(chunk_count: int) -> str:
    if chunk_count == 1:
        return "small source text"
    stride = CHUNK_CHARACTERS - OVERLAP_CHARACTERS
    return "x" * (CHUNK_CHARACTERS + ((chunk_count - 1) * stride))


def _evidence(url: str, chunk_count: int) -> Evidence:
    return Evidence(
        url=url,
        requested_url=url,
        redirect_result="no_redirect",
        retrieved_at=datetime.now(UTC),
        content_type="text/html",
        text=_text_for_chunks(chunk_count),
        content_hash=f"sha256:{url.rsplit('/', maxsplit=1)[-1]}",
        extraction_method="readability",
    )


def test_summary_batch_planner_groups_small_sources_up_to_chunk_budget() -> None:
    items = [
        SummaryWorkItem("https://example.com/a", 3),
        SummaryWorkItem("https://example.com/b", 3),
        SummaryWorkItem("https://example.com/c", 3),
        SummaryWorkItem("https://example.com/d", 3),
        SummaryWorkItem("https://example.com/e", 3),
    ]

    batches = plan_summary_batches(items)

    assert [batch.urls for batch in batches] == [tuple(item.url for item in items)]
    assert batches[0].source_count == 5
    assert batches[0].total_chunk_count == 15
    assert batches[0].oversized is False


def test_summary_batch_planner_splits_when_total_chunks_would_exceed_budget() -> None:
    items = [
        SummaryWorkItem("https://example.com/a", 5),
        SummaryWorkItem("https://example.com/b", 5),
        SummaryWorkItem("https://example.com/c", 6),
        SummaryWorkItem("https://example.com/d", 4),
    ]

    batches = plan_summary_batches(items)

    assert [batch.urls for batch in batches] == [
        ("https://example.com/a", "https://example.com/b"),
        ("https://example.com/c", "https://example.com/d"),
    ]
    assert [batch.total_chunk_count for batch in batches] == [10, 10]


def test_summary_batch_planner_isolates_oversized_sources_without_blocking_them() -> None:
    items = [
        SummaryWorkItem("https://example.com/small-before", 2),
        SummaryWorkItem("https://example.com/oversized", 16),
        SummaryWorkItem("https://example.com/small-after", 2),
    ]

    batches = plan_summary_batches(items)

    assert [batch.urls for batch in batches] == [
        ("https://example.com/small-before",),
        ("https://example.com/oversized",),
        ("https://example.com/small-after",),
    ]
    assert [batch.total_chunk_count for batch in batches] == [2, 16, 2]
    assert [batch.oversized for batch in batches] == [False, True, False]


def test_summary_automation_batches_relevant_urls_by_stored_evidence_chunks(
    monkeypatch,
) -> None:
    workspace_id, run_id = uuid4(), uuid4()
    urls = [f"https://example.com/source-{index}" for index in range(1, 6)]
    evidence_by_url = {
        urls[0]: _evidence(urls[0], 5),
        urls[1]: _evidence(urls[1], 5),
        urls[2]: _evidence(urls[2], 6),
        urls[3]: _evidence(urls[3], 16),
        urls[4]: _evidence(urls[4], 2),
    }
    candidates = [
        SourceCandidate(
            title=f"Source {index}",
            url=url,
            snippet="",
            rank=index,
            preflight_content_hash=evidence_by_url[url].content_hash,
        )
        for index, url in enumerate(urls, start=1)
    ]
    run = ResearchRun(
        id=run_id,
        question="chunk-aware batching",
        status="summarizing",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        sources=candidates,
        evidence=list(evidence_by_url.values()),
    )
    work_set = EvidenceSummaryWorkSet(
        id=uuid4(), workspace_id=workspace_id, run_id=run_id, status="waiting"
    )

    class FakeExecutionStore:
        async def get_work_set(self, *_):
            return None

        async def create_work_set(self, *_):
            return work_set

        async def refresh_work_set(self, *_):
            return work_set

    class FakeResearchStore:
        async def get_run(self, *_):
            return run

    automation = EvidenceSummaryAutomation(
        object(), FakeExecutionStore(), FakeResearchStore(), object()
    )
    batches: list[list[str]] = []

    async def start_for_urls(
        _workspace_id, _run_id, batch, _continuation, _work_set_id
    ):
        batches.append(batch)
        return SimpleNamespace(id=uuid4())

    monkeypatch.setattr(automation, "start_for_urls", start_for_urls)

    result = asyncio.run(
        automation.start_for_relevant_urls(
            workspace_id, run_id, urls, SimpleNamespace()
        )
    )

    assert batches == [
        [urls[0], urls[1]],
        [urls[2]],
        [urls[3]],
        [urls[4]],
    ]
    assert result == work_set
