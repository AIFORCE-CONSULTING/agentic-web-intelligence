"""End-to-end tests for the unified LangGraph across typed service boundaries."""

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.agent_runtime.research_workflow import build_research_workflow
from app.agentic_research.contracts import ResearchTopic, TopicCoverage, TopicPlan
from app.agentic_research.workflow_nodes import platform_research_nodes
from app.web_research.contracts import (
    ResearchRun,
    SearchResponse,
    SearchResult,
    SourceCandidate,
    ToolProviderError,
)


class Harness:
    def __init__(
        self,
        *,
        source_count: int = 2,
        blocked: set[str] | None = None,
        malformed: set[str] | None = None,
    ) -> None:
        self.workspace_id = uuid4()
        self.run_id = uuid4()
        self.source_count = source_count
        self.blocked = blocked or set()
        self.malformed = malformed or set()
        self.sources: dict[str, SourceCandidate] = {}
        self.associations = []
        self.relevant = set()
        self.qualified = set()
        self.search_queries: set[str] = set()
        self.gap_rounds = 0
        self.preflight_scheduled = False
        self.summary_urls: list[str] = []
        self.report_created = False
        self.runtime_run_id = uuid4()
        self.runtime_step_id = uuid4()
        self.authorization_requests = []
        self.authorization_decisions = {}
        self.mcp_calls = []
        self.provider_calls = 0
        self.fail_search = False
        self.failures = []

    async def plan(self, *_: object) -> TopicPlan:
        return TopicPlan(
            root=[
                ResearchTopic(
                    topic_id="identity",
                    topic="How websites communicate autonomous agent identity",
                    search_query="agent website identity",
                ),
                ResearchTopic(
                    topic_id="provenance",
                    topic="How websites communicate content provenance signals",
                    search_query="website content provenance",
                ),
            ]
        )

    async def ensure_research_assignment(self, *_: object) -> object:
        return SimpleNamespace(
            id=self.runtime_run_id,
            steps=[
                SimpleNamespace(
                    id=self.runtime_step_id,
                    role="researcher",
                    status="active",
                )
            ],
        )

    async def authorize_request(self, request: object) -> object:
        self.authorization_requests.append(request)
        query = str(request.arguments["query"])
        if query in self.search_queries:
            return SimpleNamespace(id=uuid4(), decision="deny")
        self.search_queries.add(query)
        decision = SimpleNamespace(id=uuid4(), decision="allow")
        self.authorization_decisions[decision.id] = request
        return decision

    async def invoke_authorized(
        self, correlation: object, arguments: object, authority: object
    ) -> SearchResponse:
        assert authority is self
        request = self.authorization_decisions[correlation.authorization_decision_id]
        assert correlation.request_id == request.request_id
        assert correlation.runtime_run_id == request.runtime_run_id
        assert correlation.runtime_step_id == request.runtime_step_id
        self.mcp_calls.append(correlation)
        self.provider_calls += 1
        if self.fail_search:
            raise ToolProviderError("provider offline")
        return await self.search(str(arguments["query"]), int(arguments["max_results"]))

    async def register_discovered_source(self, *_: object) -> bool:
        return True

    async def begin_gap_search_round(self, *_: object) -> int | None:
        if self.gap_rounds >= 2:
            return None
        self.gap_rounds += 1
        return self.gap_rounds

    async def search(self, query: str, limit: int) -> SearchResponse:
        slug = "identity" if "identity" in query else "provenance"
        return SearchResponse(
            query=query,
            results=[
                SearchResult(title=f"{slug}-{index}", url=f"https://{slug}{index}.example")
                for index in range(1, min(limit, self.source_count) + 1)
            ],
        )

    async def save_new_sources(
        self, _run_id: object, sources: list[SourceCandidate], _limit: int
    ) -> list[SourceCandidate]:
        stored = []
        for source in sources:
            if source.url not in self.sources:
                self.sources[source.url] = source
                stored.append(source)
        return stored

    async def record_discovered_sources(self, *_: object) -> None:
        for association in _[-1]:
            if association not in self.associations:
                self.associations.append(association)

    async def list_discovered_sources(self, *_: object):
        return self.associations

    async def preflight_run_authorized(self, *_: object) -> None:
        for url in _[-1]:
            source = self.sources[url]
            status = "review_required" if url in self.blocked else "ready_to_extract"
            self.sources[url] = source.model_copy(
                update={
                    "preflight_status": status,
                    "preflight_content_hash": f"hash:{url}",
                    "preflight_final_url": url,
                }
            )

    async def schedule(self, *_: object) -> None:
        self.preflight_scheduled = True

    async def get_run(self, *_: object) -> ResearchRun:
        now = datetime.now(UTC)
        return ResearchRun(
            id=self.run_id,
            question="Research identity and provenance",
            status="discovering",
            created_at=now,
            updated_at=now,
            sources=list(self.sources.values()),
        )

    async def transition_status(self, *args: object, **kwargs: object) -> bool:
        self.failures.append((args, kwargs))
        return True

    async def evaluate(
        self, _workspace: object, _run: object, topic_id: str, url: str, _hash: str
    ) -> object:
        decision = "model_failure" if url in self.malformed else "relevant"
        if decision == "relevant":
            self.relevant.add((topic_id, url))
        return SimpleNamespace(decision=decision)

    async def start_for_urls(
        self,
        _workspace: object,
        _run: object,
        urls: list[str],
        _continuation: object | None = None,
    ) -> object:
        self.summary_urls.extend(urls)
        return SimpleNamespace(status="completed")

    async def qualify_evidence(
        self, _workspace: object, _run: object, topic_id: str, url: str, _hash: str
    ) -> object:
        if (topic_id, url) in self.relevant:
            self.qualified.add((topic_id, url))
        return SimpleNamespace(counts_toward_topic=(topic_id, url) in self.qualified)

    async def list_topic_coverage(self, *_: object) -> list[TopicCoverage]:
        return [
            TopicCoverage(
                topic_id=topic_id,
                topic=topic_id,
                search_query=topic_id,
                status=(
                    "covered"
                    if any(item[0] == topic_id for item in self.qualified)
                    else "uncovered"
                ),
            )
            for topic_id in ("identity", "provenance")
        ]

    async def missing_topic_query(self, _workspace: object, topic: ResearchTopic, _: object) -> str:
        return f"{topic.topic_id} missing evidence round {self.gap_rounds}"

    async def final_report(self, *_: object) -> object:
        self.report_created = True
        assert all(url in self.summary_urls for _, url in self.qualified)
        return SimpleNamespace(markdown="# Report")


def run(harness: Harness, source_limit: int = 5) -> dict[str, object]:
    nodes = platform_research_nodes(
        topic_planning=harness,
        authority=harness,
        mcp=harness,
        research_store=harness,
        agentic_store=harness,
        preflight=harness,
        preflight_temporal=harness,
        relevance=harness,
        summaries=harness,
        reporting=harness,
    )
    return asyncio.run(
        build_research_workflow(nodes).compile().ainvoke(
            {
                "workspace_id": harness.workspace_id,
                "run_id": harness.run_id,
                "question": "Research identity and provenance",
                "source_limit": source_limit,
                "stage": "requested",
                "gap_search_rounds": 0,
                "uncovered_topic_ids": [],
            }
        )
    )


def test_direct_workflow_enforces_total_limit_and_excludes_unapproved_evidence() -> None:
    harness = Harness(source_count=2, blocked={"https://identity1.example"})

    result = run(harness, source_limit=2)

    assert result["stage"] == "completed"
    assert len(harness.sources) == 2
    assert "https://identity1.example" not in harness.summary_urls
    assert harness.gap_rounds == 2
    assert harness.report_created is True


def test_malformed_relevance_result_never_reaches_summaries_or_report() -> None:
    harness = Harness(source_count=1, malformed={"https://identity1.example"})

    result = run(harness, source_limit=2)

    assert result["stage"] == "completed"
    assert "https://identity1.example" not in harness.summary_urls
    assert "https://provenance1.example" in harness.summary_urls
    assert harness.gap_rounds == 2


def test_large_batch_uses_temporal_and_stops_before_model_context() -> None:
    harness = Harness(source_count=3)

    result = run(harness, source_limit=5)

    assert result["stage"] == "awaiting_preflight"
    assert harness.preflight_scheduled is True
    assert harness.relevant == set()
    assert harness.summary_urls == []
    assert harness.report_created is False


def test_replay_does_not_duplicate_sources() -> None:
    harness = Harness(source_count=1)

    run(harness, source_limit=2)
    first_urls = set(harness.sources)
    run(harness, source_limit=2)

    assert set(harness.sources) == first_urls
    assert len(harness.sources) == len(first_urls)


def test_every_mcp_search_has_one_matching_prior_allow_decision() -> None:
    harness = Harness(source_count=1)

    run(harness, source_limit=2)

    assert harness.mcp_calls
    assert len(harness.mcp_calls) == len(harness.authorization_decisions)
    for correlation in harness.mcp_calls:
        request = harness.authorization_decisions[
            correlation.authorization_decision_id
        ]
        assert correlation.request_id == request.request_id
        assert correlation.research_run_id == request.research_run_id
        assert correlation.tool_name == request.action


def test_mismatched_authorization_stops_before_provider_invocation() -> None:
    harness = Harness(source_count=1)

    async def reject_mismatch(correlation, _arguments, _authority):
        request = harness.authorization_decisions[correlation.authorization_decision_id]
        assert correlation.request_id == request.request_id
        raise RuntimeError("No matching stored allow decision exists.")

    harness.invoke_authorized = reject_mismatch

    with pytest.raises(RuntimeError, match="matching stored allow"):
        run(harness, source_limit=2)

    assert harness.provider_calls == 0


def test_search_provider_outage_records_retryable_dependency_failure() -> None:
    harness = Harness(source_count=1)
    harness.fail_search = True

    with pytest.raises(ToolProviderError, match="provider offline"):
        run(harness, source_limit=2)

    assert harness.failures
    _, failure = harness.failures[0]
    assert failure["failure_code"] == "search_unavailable"
    assert failure["failed_stage"] == "discovering"
    assert failure["retryable"] is True


def test_empty_search_result_is_not_a_provider_failure() -> None:
    harness = Harness(source_count=0)

    result = run(harness, source_limit=2)

    assert result["stage"] == "completed"
    assert harness.failures == []
