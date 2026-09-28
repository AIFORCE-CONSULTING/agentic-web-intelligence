"""Focused contracts for production-backed research workflow nodes."""

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from app.agentic_research.contracts import ResearchTopic
from app.agentic_research.workflow_nodes import (
    evidence_acquisition_node,
    topic_search_node,
)
from app.web_research.contracts import ResearchRun, SearchResponse, SearchResult


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


class Authority:
    def __init__(self) -> None:
        self.runtime_run_id = uuid4()
        self.runtime_step_id = uuid4()
        self.requests = []
        self.decisions = {}

    async def ensure_research_assignment(self, *_: object) -> object:
        return SimpleNamespace(
            id=self.runtime_run_id,
            steps=[SimpleNamespace(id=self.runtime_step_id, role="researcher", status="active")],
        )

    async def authorize_request(self, request: object) -> object:
        self.requests.append(request)
        decision = SimpleNamespace(id=uuid4(), decision="allow")
        self.decisions[decision.id] = request
        return decision

    async def register_discovered_source(self, *_: object) -> bool:
        return True


class Mcp:
    def __init__(self, authority: Authority, search: object) -> None:
        self.authority = authority
        self.search = search

    async def invoke_authorized(self, correlation, arguments, authority):
        assert authority is self.authority
        request = self.authority.decisions[correlation.authorization_decision_id]
        assert request.request_id == correlation.request_id
        return await self.search(arguments["query"], arguments["max_results"])


class ResearchStore:
    def __init__(self) -> None:
        self.saved: list[object] = []

    async def save_new_sources(self, _run_id: object, sources: list[object], limit: int):
        self.saved = sources
        assert len(sources) <= limit
        return sources

    async def get_run(self, _workspace_id: object, run_id: object) -> ResearchRun:
        now = datetime.now(UTC)
        return ResearchRun(
            id=run_id,
            question="Compare identity and provenance",
            status="discovering",
            created_at=now,
            updated_at=now,
        )


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

    authority = Authority()

    update = asyncio.run(
        topic_search_node(
            authority, Mcp(authority, search), research_store, agentic_store
        )(state())
    )

    assert update["stage"] == "sources_discovered"
    assert len(update["new_source_urls"]) == 3
    assert len(set(update["new_source_urls"])) == 3
    assert len(agentic_store.associations) == 4


class DirectPreflight:
    def __init__(self) -> None:
        self.called = False

    async def preflight_run_authorized(self, *args: object) -> None:
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
        evidence_acquisition_node(direct, temporal, object(), object())(
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
        evidence_acquisition_node(direct, temporal, object(), object())(
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
