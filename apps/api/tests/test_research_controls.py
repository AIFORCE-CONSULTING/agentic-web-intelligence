"""Tests for application-owned agentic research limits and records."""

import asyncio
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.agent_runtime.contracts import (
    CapabilityRequest,
    McpExecutionCorrelation,
    RuntimeRun,
    RuntimeStep,
)
from app.agent_runtime.service import RuntimePlanError, RuntimeService
from app.agentic_research.contracts import CapabilityRequestDecision, ResearchControlState
from app.agentic_research.control import AgenticResearchControlService
from app.web_research.contracts import ResearchRun


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


class StoredAuthorityFacts:
    def __init__(self) -> None:
        now = datetime.now(UTC)
        self.workspace_id = uuid4()
        self.research_run_id = uuid4()
        self.runtime_run_id = uuid4()
        self.step_id = uuid4()
        self.runtime = RuntimeRun(
            id=self.runtime_run_id,
            workspace_id=self.workspace_id,
            research_run_id=self.research_run_id,
            goal="Research agent identity",
            status="executing",
            created_at=now,
            updated_at=now,
            steps=[
                RuntimeStep(
                    id=self.step_id,
                    role="researcher",
                    title="Conduct governed research",
                    status="active",
                    allowed_capabilities=["web.search", "web.extract"],
                    attempt_count=1,
                    idempotency_key="researcher:test",
                    timeout_seconds=300,
                    created_at=now,
                    updated_at=now,
                )
            ],
        )
        self.research = ResearchRun(
            id=self.research_run_id,
            question="Research agent identity",
            status="discovering",
            status_version=2,
            created_at=now,
            updated_at=now,
        )
        self.decisions = []
        self.discovered = {"https://example.com/evidence"}
        self.query_available = True
        self.attempt_available = True

    async def get_run(self, run_id, workspace_id=None):
        del workspace_id
        return self.runtime if run_id == self.runtime_run_id else None

    async def record_authorization_decision(self, decision):
        self.decisions.append(decision)
        return decision

    async def authorization_decision(self, decision_id):
        return next(
            (decision for decision in self.decisions if decision.id == decision_id),
            None,
        )

    async def source_is_discovered(self, research_run_id, source_url):
        return research_run_id == self.research_run_id and source_url in self.discovered

    async def reserve_query(self, *_):
        return self.query_available

    async def reserve_source_attempt(self, *_):
        return self.attempt_available


class StoredResearchReader:
    def __init__(self, facts: StoredAuthorityFacts) -> None:
        self.facts = facts

    async def get_run(self, workspace_id, run_id):
        if workspace_id != self.facts.workspace_id or run_id != self.facts.research_run_id:
            return None
        return self.facts.research


def stored_request(facts: StoredAuthorityFacts, **updates) -> CapabilityRequest:
    values = {
        "workspace_id": facts.workspace_id,
        "runtime_run_id": facts.runtime_run_id,
        "runtime_step_id": facts.step_id,
        "research_run_id": facts.research_run_id,
        "research_status": facts.research.status,
        "research_status_version": facts.research.status_version,
        "topic_id": "agent-identity",
        "action": "web.search",
        "resource_type": "research_query",
        "resource_id": "agent-identity",
        "arguments": {"query": "agent identity standards", "max_results": 10},
        "request_id": uuid4(),
        "purpose": "Find evidence about agent identity",
    }
    values.update(updates)
    return CapabilityRequest.model_validate(values)


def authorize(facts: StoredAuthorityFacts, request: CapabilityRequest):
    return asyncio.run(
        RuntimeService(facts, StoredResearchReader(facts)).authorize_request(request)
    )


def test_stored_authority_allows_and_records_a_current_search_request() -> None:
    facts = StoredAuthorityFacts()

    decision = authorize(facts, stored_request(facts))

    assert decision.decision == "allow"
    assert decision.reason_code == "allowed"
    assert facts.decisions == [decision]
    assert "agent identity standards" not in str(decision.request_facts)


@pytest.mark.parametrize(
    ("mutation", "expected_reason"),
    [
        (lambda facts: setattr(facts.runtime, "status", "failed"), "run_inactive"),
        (
            lambda facts: setattr(facts.runtime.steps[0], "status", "completed"),
            "step_inactive",
        ),
        (
            lambda facts: setattr(facts.research, "status", "reporting"),
            "stale_authorization",
        ),
    ],
)
def test_stored_authority_fails_closed_for_changed_facts(mutation, expected_reason) -> None:
    facts = StoredAuthorityFacts()
    request = stored_request(facts)
    mutation(facts)

    decision = authorize(facts, request)

    assert decision.decision == "deny"
    assert decision.reason_code == expected_reason
    assert facts.decisions == [decision]


@pytest.mark.parametrize(
    ("prepare", "request_updates", "expected_reason"),
    [
        (
            lambda facts: setattr(facts.runtime, "workspace_id", uuid4()),
            {},
            "wrong_workspace",
        ),
        (
            lambda facts: setattr(facts.runtime, "research_run_id", uuid4()),
            {},
            "wrong_research_task",
        ),
        (
            lambda facts: facts.runtime.steps[0].allowed_capabilities.clear(),
            {},
            "capability_not_granted",
        ),
        (
            lambda facts: setattr(facts.research, "status", "reporting"),
            {"research_status": "reporting"},
            "invalid_stage",
        ),
        (
            lambda facts: None,
            {"arguments": {"query": "agent identity", "max_results": 500}},
            "malformed_context",
        ),
    ],
)
def test_authority_default_deny_matrix(prepare, request_updates, expected_reason) -> None:
    facts = StoredAuthorityFacts()
    prepare(facts)

    decision = authorize(facts, stored_request(facts, **request_updates))

    assert decision.decision == "deny"
    assert decision.reason_code == expected_reason
    assert facts.decisions == [decision]


def test_extraction_requires_stored_source_scope_and_attempt_budget() -> None:
    facts = StoredAuthorityFacts()
    facts.research.status = "acquiring"
    request = stored_request(
        facts,
        research_status="acquiring",
        action="web.extract",
        resource_type="source",
        resource_id="https://not-discovered.example/article",
        arguments={"url": "https://not-discovered.example/article"},
    )

    decision = authorize(facts, request)

    assert decision.decision == "deny"
    assert decision.reason_code == "source_not_discovered"

    facts.attempt_available = False
    request = stored_request(
        facts,
        research_status="acquiring",
        action="web.extract",
        resource_type="source",
        resource_id="https://example.com/evidence",
        arguments={"url": "https://example.com/evidence"},
    )
    decision = authorize(facts, request)
    assert decision.reason_code == "attempt_limit_exhausted"


def test_duplicate_query_is_denied_and_recorded() -> None:
    facts = StoredAuthorityFacts()
    facts.query_available = False

    decision = authorize(facts, stored_request(facts))

    assert decision.decision == "deny"
    assert decision.reason_code == "retry_limit_exhausted"
    assert facts.decisions == [decision]


def test_execution_recheck_denies_when_research_changes_after_authorization() -> None:
    facts = StoredAuthorityFacts()
    service = RuntimeService(facts, StoredResearchReader(facts))
    request = stored_request(facts)
    decision = asyncio.run(service.authorize_request(request))
    facts.research.status_version += 1
    correlation = McpExecutionCorrelation(
        workspace_id=request.workspace_id,
        research_run_id=request.research_run_id,
        runtime_run_id=request.runtime_run_id,
        runtime_step_id=request.runtime_step_id,
        authorization_decision_id=decision.id,
        request_id=request.request_id,
        tool_name=request.action,
        resource_type=request.resource_type,
        resource_id=request.resource_id,
    )

    with pytest.raises(RuntimePlanError, match="changed"):
        asyncio.run(service.verify_execution(correlation))

    assert facts.decisions[-1].decision == "deny"
    assert facts.decisions[-1].reason_code == "stale_authorization"


@pytest.mark.parametrize(
    "field",
    [
        "workspace_id",
        "research_run_id",
        "runtime_run_id",
        "runtime_step_id",
        "request_id",
        "authorization_decision_id",
        "tool_name",
        "resource_type",
        "resource_id",
    ],
)
def test_execution_requires_every_correlation_identity_to_match(field: str) -> None:
    facts = StoredAuthorityFacts()
    service = RuntimeService(facts, StoredResearchReader(facts))
    request = stored_request(facts)
    decision = asyncio.run(service.authorize_request(request))
    values = {
        "workspace_id": request.workspace_id,
        "research_run_id": request.research_run_id,
        "runtime_run_id": request.runtime_run_id,
        "runtime_step_id": request.runtime_step_id,
        "authorization_decision_id": decision.id,
        "request_id": request.request_id,
        "tool_name": request.action,
        "resource_type": request.resource_type,
        "resource_id": request.resource_id,
    }
    if field in {"resource_id"}:
        values[field] = "different-resource"
    elif field == "tool_name":
        values[field] = "web.extract"
    elif field == "resource_type":
        values[field] = "source"
    else:
        values[field] = uuid4()

    with pytest.raises(RuntimePlanError, match="matching stored allow"):
        asyncio.run(
            service.verify_execution(McpExecutionCorrelation.model_validate(values))
        )
