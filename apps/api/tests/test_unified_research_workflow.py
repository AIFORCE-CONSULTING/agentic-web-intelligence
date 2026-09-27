"""Tests for the canonical topic-driven LangGraph structure."""

import asyncio
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest

import app.agent_runtime.research_workflow as research_workflow_module
from app.agent_runtime.research_workflow import (
    ResearchCheckpointLifecycle,
    ResearchWorkflowNodes,
    ResearchWorkflowState,
    build_research_workflow,
)
from app.durable_execution.contracts import UNIFIED_RESEARCH_WORKFLOW_VERSION


class FakeCleanupStore:
    def __init__(self, candidates: list | None = None, backlog: int = 0) -> None:
        self.candidates = candidates or []
        self.backlog = backlog
        self.requested_limits: list[int] = []
        self.records: list[tuple] = []

    async def checkpoint_cleanup_candidates(self, limit: int = 100) -> list:
        self.requested_limits.append(limit)
        return self.candidates[:limit]

    async def checkpoint_cleanup_backlog(self) -> int:
        return self.backlog

    async def record_checkpoint_cleanup(
        self, run_id, outcome: str, explanation: str | None = None
    ) -> None:
        self.records.append((run_id, outcome, explanation))


class FakeSaver:
    def __init__(self, *, setup_error: Exception | None = None) -> None:
        self.setup_error = setup_error
        self.setup_calls = 0
        self.deleted: list[str] = []
        self.delete_failures: set[str] = set()
        self.checkpoints: list[Any] = []

    async def setup(self) -> None:
        self.setup_calls += 1
        if self.setup_error:
            raise self.setup_error

    async def adelete_thread(self, thread_id: str) -> None:
        if thread_id in self.delete_failures:
            raise RuntimeError("delete failed")
        self.deleted.append(thread_id)

    async def alist(
        self, config: dict | None, *, limit: int | None = None
    ) -> AsyncIterator[Any]:
        del config
        for checkpoint in self.checkpoints[:limit]:
            yield checkpoint


class FakeSaverContext(AbstractAsyncContextManager):
    def __init__(self, saver: FakeSaver) -> None:
        self.saver = saver
        self.exited = False

    async def __aenter__(self) -> FakeSaver:
        return self.saver

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        del exc_type, exc_value, traceback
        self.exited = True


def node(
    name: str,
    visited: list[str],
    update: ResearchWorkflowState | None = None,
) -> Callable[[ResearchWorkflowState], object]:
    async def run(_: ResearchWorkflowState) -> ResearchWorkflowState:
        visited.append(name)
        return update or {}

    return run


def nodes(
    visited: list[str],
    *,
    coverage: ResearchWorkflowState,
    gap_result: ResearchWorkflowState | None = None,
) -> ResearchWorkflowNodes:
    async def assess_coverage(_: ResearchWorkflowState) -> ResearchWorkflowState:
        visited.append("assess_topic_coverage")
        if "search_missing_topic" in visited:
            return {"stage": "coverage_complete", "uncovered_topic_ids": []}
        return coverage

    return ResearchWorkflowNodes(
        plan_topics=node("plan_topics", visited, {"stage": "topics_planned"}),
        search_topics=node("search_topics", visited, {"stage": "sources_discovered"}),
        acquire_evidence=node("acquire_evidence", visited, {"stage": "evidence_acquired"}),
        evaluate_relevance=node(
            "evaluate_relevance", visited, {"stage": "relevance_decided"}
        ),
        summarize_evidence=node(
            "summarize_evidence", visited, {"stage": "summaries_stored"}
        ),
        assess_topic_coverage=assess_coverage,
        search_missing_topic=node(
            "search_missing_topic",
            visited,
            gap_result
            or {
                "stage": "evidence_acquired",
                "gap_search_rounds": 2,
                "uncovered_topic_ids": [],
            },
        ),
        generate_final_report=node(
            "generate_final_report", visited, {"stage": "report_stored"}
        ),
        complete_research=node("complete_research", visited, {"stage": "completed"}),
    )


def initial_state() -> ResearchWorkflowState:
    return {
        "workspace_id": uuid4(),
        "run_id": uuid4(),
        "question": "How should agents evaluate web evidence?",
        "source_limit": 20,
        "stage": "requested",
        "topics": [],
        "uncovered_topic_ids": [],
        "gap_search_rounds": 0,
    }


def test_checkpoint_lifecycle_uses_stable_thread_and_versioned_namespace() -> None:
    run_id = uuid4()

    assert ResearchCheckpointLifecycle.graph_config(run_id) == {
        "configurable": {
            "thread_id": str(run_id),
            "checkpoint_ns": UNIFIED_RESEARCH_WORKFLOW_VERSION,
        }
    }


def test_checkpoint_start_sets_up_saver_and_retries_oldest_cleanup_batch() -> None:
    run_ids = [uuid4(), uuid4()]
    store = FakeCleanupStore(run_ids)
    saver = FakeSaver()
    context = FakeSaverContext(saver)
    lifecycle = ResearchCheckpointLifecycle(
        None,
        store,
        startup_cleanup_limit=100,
        saver_context_factory=lambda: context,
    )

    asyncio.run(lifecycle.start())

    assert saver.setup_calls == 1
    assert store.requested_limits == [100]
    assert saver.deleted == [str(run_id) for run_id in run_ids]
    assert [record[1] for record in store.records] == ["succeeded", "succeeded"]

    asyncio.run(lifecycle.stop())
    assert context.exited is True


def test_checkpoint_setup_failure_stays_unavailable_without_fallback() -> None:
    saver = FakeSaver(setup_error=RuntimeError("database unavailable"))
    context = FakeSaverContext(saver)
    lifecycle = ResearchCheckpointLifecycle(
        None,
        FakeCleanupStore(),
        saver_context_factory=lambda: context,
    )

    with pytest.raises(RuntimeError, match="checkpoint persistence is unavailable"):
        asyncio.run(lifecycle.start())

    readiness = asyncio.run(lifecycle.readiness())
    assert readiness.ready is False
    assert "unavailable" in readiness.detail
    assert context.exited is True


def test_default_checkpoint_serializer_disables_pickle_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    saver = FakeSaver()
    captured: dict[str, Any] = {}

    def from_conn_string(connection_string: str, *, serde: Any) -> FakeSaverContext:
        captured["connection_string"] = connection_string
        captured["serde"] = serde
        return FakeSaverContext(saver)

    monkeypatch.setattr(
        research_workflow_module.AsyncPostgresSaver,
        "from_conn_string",
        from_conn_string,
    )
    lifecycle = ResearchCheckpointLifecycle(
        "postgresql://checkpoint-test",
        FakeCleanupStore(),
    )

    asyncio.run(lifecycle.start())

    assert captured["connection_string"] == "postgresql://checkpoint-test"
    assert captured["serde"].pickle_fallback is False


def test_checkpoint_cleanup_failure_is_audited_and_keeps_degraded_readiness() -> None:
    run_id = uuid4()
    store = FakeCleanupStore([run_id], backlog=1)
    saver = FakeSaver()
    saver.delete_failures.add(str(run_id))
    lifecycle = ResearchCheckpointLifecycle(
        None,
        store,
        saver_context_factory=lambda: FakeSaverContext(saver),
    )

    asyncio.run(lifecycle.start())
    readiness = asyncio.run(lifecycle.readiness())

    assert store.records[0][0:2] == (run_id, "failed")
    assert readiness.ready is False
    assert readiness.backlog == 1


def test_obsolete_checkpoint_cleanup_uses_official_thread_deletion_once() -> None:
    saver = FakeSaver()
    saver.checkpoints = [
        SimpleNamespace(config={"configurable": {"thread_id": "old-a"}}),
        SimpleNamespace(config={"configurable": {"thread_id": "old-a"}}),
        SimpleNamespace(config={"configurable": {"thread_id": "old-b"}}),
    ]
    lifecycle = ResearchCheckpointLifecycle(
        None,
        FakeCleanupStore(),
        saver_context_factory=lambda: FakeSaverContext(saver),
    )
    asyncio.run(lifecycle.start())

    deleted = asyncio.run(lifecycle.delete_obsolete_threads(limit=100))

    assert deleted == 2
    assert saver.deleted == ["old-a", "old-b"]


def test_complete_coverage_runs_each_research_stage_once() -> None:
    visited: list[str] = []
    workflow = build_research_workflow(
        nodes(visited, coverage={"stage": "coverage_complete", "uncovered_topic_ids": []})
    ).compile()

    result = asyncio.run(workflow.ainvoke(initial_state()))

    assert result["stage"] == "completed"
    assert visited == [
        "plan_topics",
        "search_topics",
        "acquire_evidence",
        "evaluate_relevance",
        "summarize_evidence",
        "assess_topic_coverage",
        "generate_final_report",
        "complete_research",
    ]


def test_missing_topic_uses_one_bounded_gap_search_before_reporting() -> None:
    visited: list[str] = []
    workflow = build_research_workflow(
        nodes(
            visited,
            coverage={
                "stage": "coverage_incomplete",
                "gap_search_rounds": 1,
                "uncovered_topic_ids": ["agent-identity"],
            },
        )
    ).compile()

    result = asyncio.run(workflow.ainvoke(initial_state()))

    assert result["stage"] == "completed"
    assert visited.count("search_missing_topic") == 1
    assert visited.count("acquire_evidence") == 2
    assert result["gap_search_rounds"] == 2


def test_exhausted_gap_limit_generates_report_without_another_search() -> None:
    visited: list[str] = []
    workflow = build_research_workflow(
        nodes(
            visited,
            coverage={
                "stage": "coverage_incomplete",
                "gap_search_rounds": 2,
                "uncovered_topic_ids": ["agent-identity"],
            },
        )
    ).compile()

    result = asyncio.run(workflow.ainvoke(initial_state()))

    assert result["stage"] == "completed"
    assert "search_missing_topic" not in visited


def test_review_required_evidence_stops_before_report_generation() -> None:
    visited: list[str] = []
    workflow = build_research_workflow(
        nodes(visited, coverage={"stage": "awaiting_review"})
    ).compile()

    result = asyncio.run(workflow.ainvoke(initial_state()))

    assert result["stage"] == "awaiting_review"
    assert "generate_final_report" not in visited
    assert "complete_research" not in visited
