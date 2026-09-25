"""Focused contracts for production-backed research workflow nodes."""

import asyncio
from types import SimpleNamespace
from uuid import uuid4

from app.agentic_research.contracts import ResearchTopic
from app.agentic_research.workflow_nodes import (
    evidence_acquisition_node,
    topic_search_node,
)
from app.web_research.contracts import SearchResponse, SearchResult


def state(**updates: object) -> dict[str, object]:
    values: dict[str, object] = {
        "workspace_id": uuid4(),
        "run_id": uuid4(),
        "question": "Compare identity and provenance",
        "source_limit": 3,
        "stage": "topics_planned",
        "topics": [
            ResearchTopic(
                topic_id="identity",
                topic="How agent identity is declared by websites",
                search_query="agent website identity",
            ),
            ResearchTopic(
                topic_id="provenance",
                topic="How websites communicate content provenance",
                search_query="website content provenance",
            ),
        ],
        "gap_search_rounds": 0,
        "uncovered_topic_ids": [],
    }
    values.update(updates)
    return values


class AcceptingControl:
    async def consider_request(self, *args: object, **kwargs: object) -> object:
        return SimpleNamespace(decision="accepted")


class ResearchStore:
    def __init__(self) -> None:
        self.saved: list[object] = []

    async def save_new_sources(self, _run_id: object, sources: list[object], limit: int):
        self.saved = sources
        assert len(sources) <= limit
        return sources


class AgenticStore:
    def __init__(self) -> None:
        self.associations: list[object] = []

    async def record_discovered_sources(
        self, _workspace_id: object, _run_id: object, associations: list[object]
    ) -> None:
        self.associations = associations


def test_topic_search_round_robins_unique_results_with_one_total_limit() -> None:
    research_store = ResearchStore()
    agentic_store = AgenticStore()

    async def search(query: str, limit: int) -> SearchResponse:
        shared = SearchResult(title="Shared", url="https://example.com/shared")
        unique = SearchResult(title=query, url=f"https://example.com/{query.split()[1]}")
        return SearchResponse(query=query, results=[shared, unique][:limit])

    update = asyncio.run(
        topic_search_node(
            AcceptingControl(), research_store, agentic_store, search
        )(state())
    )

    assert update["stage"] == "sources_discovered"
    assert len(update["new_source_urls"]) == 3
    assert len(set(update["new_source_urls"])) == 3
    assert len(agentic_store.associations) == 4


class DirectPreflight:
    def __init__(self) -> None:
        self.called = False

    async def preflight_run(self, *args: object) -> None:
        self.called = True


class TemporalPreflight:
    def __init__(self) -> None:
        self.called = False

    async def schedule(self, *args: object) -> None:
        self.called = True


def test_acquisition_uses_direct_service_for_two_sources() -> None:
    direct = DirectPreflight()
    temporal = TemporalPreflight()

    update = asyncio.run(
        evidence_acquisition_node(direct, temporal)(
            state(new_source_urls=["https://a.example", "https://b.example"])
        )
    )

    assert update["stage"] == "evidence_acquired"
    assert direct.called is True
    assert temporal.called is False


def test_acquisition_pauses_after_temporal_accepts_larger_batch() -> None:
    direct = DirectPreflight()
    temporal = TemporalPreflight()

    update = asyncio.run(
        evidence_acquisition_node(direct, temporal)(
            state(
                new_source_urls=[
                    "https://a.example",
                    "https://b.example",
                    "https://c.example",
                ]
            )
        )
    )

    assert update["stage"] == "awaiting_preflight"
    assert direct.called is False
    assert temporal.called is True
