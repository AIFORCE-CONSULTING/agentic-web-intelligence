"""Tests for application-owned agentic research limits and records."""

import asyncio
from uuid import UUID, uuid4

from app.agentic_research.contracts import CapabilityRequestDecision, ResearchControlState
from app.agentic_research.control import AgenticResearchControlService


class FakeStore:
    def __init__(self) -> None:
        self.workspace_id = uuid4()
        self.run_id = uuid4()
        self.gap_rounds = 0
        self.queries: set[str] = set()
        self.source_attempts: dict[str, int] = {}
        self.decisions: list[CapabilityRequestDecision] = []

    async def control_state(self, workspace_id: UUID, run_id: UUID) -> ResearchControlState:
        assert workspace_id == self.workspace_id
        assert run_id == self.run_id
        return ResearchControlState(
            workspace_id=workspace_id,
            run_id=run_id,
            gap_search_rounds=self.gap_rounds,
        )

    async def reserve_search_query(
        self, _: UUID, __: UUID, ___: str, query: str, ____: str
    ) -> bool:
        normalized = " ".join(query.casefold().split())
        if normalized in self.queries:
            return False
        self.queries.add(normalized)
        return True

    async def reserve_source_attempt(
        self, _: UUID, __: UUID, ___: str, source_url: str
    ) -> bool:
        attempts = self.source_attempts.get(source_url, 0)
        if attempts >= 3:
            return False
        self.source_attempts[source_url] = attempts + 1
        return True

    async def record_capability_decision(
        self, _: UUID, __: UUID, ___: str, decision: CapabilityRequestDecision
    ) -> None:
        self.decisions.append(decision)

    async def begin_gap_search_round(
        self, workspace_id: UUID, run_id: UUID
    ) -> ResearchControlState | None:
        if self.gap_rounds >= 2:
            return None
        self.gap_rounds += 1
        return await self.control_state(workspace_id, run_id)


def consider(
    store: FakeStore,
    capability: str,
    arguments: dict[str, object],
    grants: list[str],
    discovered_urls: list[str] | None = None,
) -> CapabilityRequestDecision:
    return asyncio.run(
        AgenticResearchControlService(store).consider_request(
            store.workspace_id,
            store.run_id,
            "agent-identity",
            capability,
            arguments,
            grants,
            discovered_urls or [],
        )
    )


def test_platform_accepts_and_records_a_valid_search_request() -> None:
    store = FakeStore()

    decision = consider(
        store,
        "web.search",
        {"query": "agent identity standards", "max_results": 10},
        ["web.search"],
    )

    assert decision.decision == "accepted"
    assert store.queries == {"agent identity standards"}
    assert store.decisions == [decision]


def test_platform_denies_the_same_normalized_query_twice() -> None:
    store = FakeStore()
    first = {"query": "Agent   Identity Standards", "max_results": 10}
    second = {"query": "agent identity standards", "max_results": 10}

    assert consider(store, "web.search", first, ["web.search"]).decision == "accepted"
    duplicate = consider(store, "web.search", second, ["web.search"])

    assert duplicate.decision == "denied"
    assert "already been used" in duplicate.reason
    assert len(store.decisions) == 2


def test_platform_limits_acquisition_attempts_without_calling_a_tool() -> None:
    store = FakeStore()
    url = "https://example.com/evidence"

    outcomes = [
        consider(store, "web.extract", {"url": url}, ["web.extract"], [url]).decision
        for _ in range(4)
    ]

    assert outcomes == ["accepted", "accepted", "accepted", "denied"]
    assert store.source_attempts[url] == 3


def test_platform_owns_the_two_round_gap_search_limit() -> None:
    store = FakeStore()
    service = AgenticResearchControlService(store)

    rounds = [
        asyncio.run(service.begin_gap_search_round(store.workspace_id, store.run_id))
        for _ in range(3)
    ]

    assert [state.gap_search_rounds if state else None for state in rounds] == [1, 2, None]


def test_denied_request_records_safe_facts_not_arbitrary_values() -> None:
    store = FakeStore()

    decision = consider(
        store,
        "browser.click",
        {"selector": "#accept-all", "credential": "do-not-store"},
        ["web.search", "web.extract"],
    )

    assert decision.decision == "denied"
    assert decision.capability == "browser.click"
    assert decision.arguments == {"argument_names": ["credential", "selector"]}
    assert "do-not-store" not in str(decision.model_dump())


def test_invalid_search_is_denied_before_query_reservation() -> None:
    store = FakeStore()

    decision = consider(
        store,
        "web.search",
        {"query": "agent identity", "max_results": 500},
        ["web.search"],
    )

    assert decision.decision == "denied"
    assert store.queries == set()
    assert store.decisions == [decision]
