"""Tests for the canonical topic-driven LangGraph structure."""

import asyncio
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest
from asyncpg.pgproto.pgproto import UUID as AsyncpgUUID
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

import app.agent_runtime.research_workflow as research_workflow_module
from app.agent_runtime.research_workflow import (
    CHECKPOINT_ALLOWED_MSGPACK_MODULES,
    CanonicalResearchWorkflowNodes,
    CheckpointReadiness,
    ResearchCheckpointLifecycle,
    ResearchWorkflowConflict,
    ResearchWorkflowNodes,
    ResearchWorkflowState,
    ResearchWorkflowUnavailable,
    UnifiedResearchWorkflowEntry,
    _route_from_canonical_status,
    build_research_workflow,
)
from app.agentic_research.contracts import ResearchTopic, TopicSourceAssociation
from app.agentic_research.topic_planning import TopicPlanningUnavailable
from app.agentic_research.workflow_nodes import topic_relevance_node
from app.durable_execution.contracts import UNIFIED_RESEARCH_WORKFLOW_VERSION
from app.web_research.contracts import ResearchRun, SourceCandidate
from app.web_trust.contracts import EvidenceTrustEvaluation, TrustRuleOutcome


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


@pytest.mark.parametrize(
    ("status", "node"),
    [
        ("requested", "plan_topics"),
        ("planning", "plan_topics"),
        ("discovering", "search_topics"),
        ("acquiring", "acquire_evidence"),
        ("evaluating_relevance", "evaluate_relevance"),
        ("summarizing", "summarize_evidence"),
        ("assessing_coverage", "assess_topic_coverage"),
        ("reporting", "generate_final_report"),
    ],
)
def test_graph_entry_routes_from_canonical_research_status(
    status: str, node: str
) -> None:
    assert _route_from_canonical_status(
        {"stage": status, "canonical_status": status}  # type: ignore[typeddict-item]
    ) == node


def test_graph_entry_rejects_non_resumable_status() -> None:
    with pytest.raises(ResearchWorkflowUnavailable, match="cannot start"):
        _route_from_canonical_status(
            {"stage": "failed", "canonical_status": "failed"}
        )


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
    acquisition: ResearchWorkflowState | None = None,
    relevance: ResearchWorkflowState | None = None,
    summary: ResearchWorkflowState | None = None,
) -> ResearchWorkflowNodes:
    async def assess_coverage(_: ResearchWorkflowState) -> ResearchWorkflowState:
        visited.append("assess_topic_coverage")
        if "search_missing_topic" in visited:
            return {"stage": "coverage_complete", "uncovered_topic_ids": []}
        return coverage

    return ResearchWorkflowNodes(
        plan_topics=node("plan_topics", visited, {"stage": "topics_planned"}),
        search_topics=node("search_topics", visited, {"stage": "sources_discovered"}),
        acquire_evidence=node(
            "acquire_evidence",
            visited,
            acquisition or {"stage": "evidence_acquired"},
        ),
        evaluate_relevance=node(
            "evaluate_relevance",
            visited,
            relevance or {"stage": "relevance_decided"},
        ),
        summarize_evidence=node(
            "summarize_evidence",
            visited,
            summary or {"stage": "summaries_stored"},
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
        fail_durable_work=node("fail_durable_work", visited, {"stage": "failed"}),
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
    assert captured["serde"]._allowed_msgpack_modules == set(
        CHECKPOINT_ALLOWED_MSGPACK_MODULES
    )


def test_checkpoint_serializer_round_trips_only_approved_graph_types() -> None:
    serializer = research_workflow_module.JsonPlusSerializer(
        pickle_fallback=False,
        allowed_json_modules=(),
        allowed_msgpack_modules=CHECKPOINT_ALLOWED_MSGPACK_MODULES,
    )
    run_id = AsyncpgUUID(str(uuid4()))
    state = {
        "run_id": run_id,
        "topics": [
            ResearchTopic(
                topic_id="durable-trust",
                topic="Durable research trust",
                search_query="durable research trust",
            )
        ],
        "source_topics": [
            TopicSourceAssociation(
                topic_id="durable-trust",
                source_url="https://example.com/research",
                result_rank=1,
            )
        ],
    }

    encoded = serializer.dumps_typed(state)
    restored = serializer.loads_typed(encoded)

    assert restored == state


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
    assert readiness.ready is True
    assert readiness.backlog == 1
    assert "maintenance" in readiness.detail
    assert "does not delete completed research outputs" in readiness.detail


def test_checkpoint_cleanup_backlog_stays_start_eligible() -> None:
    lifecycle = ResearchCheckpointLifecycle(
        None,
        FakeCleanupStore(backlog=2),
        saver_context_factory=lambda: FakeSaverContext(FakeSaver()),
    )

    asyncio.run(lifecycle.start())
    readiness = asyncio.run(lifecycle.readiness())

    assert readiness.ready is True
    assert readiness.backlog == 2
    assert "execution bookmarks only" in readiness.detail


def test_checkpoint_cleanup_retry_can_succeed_after_prior_failure() -> None:
    run_id = uuid4()
    store = FakeCleanupStore([run_id], backlog=0)
    saver = FakeSaver()
    saver.delete_failures.add(str(run_id))
    lifecycle = ResearchCheckpointLifecycle(
        None,
        store,
        saver_context_factory=lambda: FakeSaverContext(saver),
    )

    asyncio.run(lifecycle.start())
    saver.delete_failures.clear()
    remaining = asyncio.run(lifecycle.retry_completed_cleanup(limit=100))

    assert remaining == 0
    assert store.requested_limits == [100, 100]
    assert [record[1] for record in store.records] == ["failed", "succeeded"]
    assert saver.deleted == [str(run_id)]


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


def test_workflow_entry_reuses_canonical_run_and_stable_checkpoint_identity() -> None:
    workspace_id = uuid4()
    run_id = uuid4()
    now = datetime.now(UTC)
    run = ResearchRun(
        id=run_id,
        question="agent identity",
        status="planning",
        created_at=now,
        updated_at=now,
    )
    graph_calls: list[tuple] = []
    assignments: list[tuple] = []

    class Store:
        async def get_or_create_run(self, *_):
            return run, False

        async def get_run(self, *_):
            return run

    class Runtime:
        async def ensure_research_assignment(self, *args):
            assignments.append(args)

    class Checkpoints:
        async def readiness(self):
            return CheckpointReadiness(True, 0, "ready")

        def graph_config(self, requested_run_id):
            return ResearchCheckpointLifecycle.graph_config(requested_run_id)

    class Graph:
        async def ainvoke(self, state, config):
            graph_calls.append((state, config))
            return state

    async def temporal_ready() -> bool:
        return True

    entry = UnifiedResearchWorkflowEntry(
        Store(), Runtime(), Checkpoints(), Graph(), temporal_ready
    )

    persisted, created = asyncio.run(
        entry.start_or_resume(workspace_id, "agent identity", 20)
    )

    assert persisted == run
    assert created is False
    assert assignments == [(workspace_id, run_id, "agent identity")]
    assert graph_calls[0][1] == ResearchCheckpointLifecycle.graph_config(run_id)
    assert graph_calls[0][0]["source_limit"] == 20


def test_workflow_entry_fails_before_record_creation_when_temporal_is_unavailable() -> None:
    class Store:
        async def get_or_create_run(self, *_):
            raise AssertionError("Readiness must pass before a record is created.")

    class Checkpoints:
        async def readiness(self):
            return CheckpointReadiness(True, 0, "ready")

    async def temporal_ready() -> bool:
        return False

    entry = UnifiedResearchWorkflowEntry(
        Store(), object(), Checkpoints(), object(), temporal_ready
    )

    with pytest.raises(ResearchWorkflowUnavailable, match="Durable execution"):
        asyncio.run(entry.start_or_resume(uuid4(), "agent identity", 20))


def test_workflow_entry_does_not_restart_completed_research() -> None:
    workspace_id, run_id = uuid4(), uuid4()
    now = datetime.now(UTC)
    run = ResearchRun(
        id=run_id,
        question="agent identity",
        status="completed",
        status_version=8,
        created_at=now,
        updated_at=now,
    )

    class Store:
        async def get_or_create_run(self, *_):
            return run, False

        async def get_run(self, *_):
            return run

    class Runtime:
        async def ensure_research_assignment(self, *_):
            return None

    class Checkpoints:
        async def readiness(self):
            return CheckpointReadiness(True, 0, "ready")

    class Graph:
        async def ainvoke(self, *_):
            raise AssertionError("Completed research must not restart the graph.")

    async def temporal_ready() -> bool:
        return True

    persisted, created = asyncio.run(
        UnifiedResearchWorkflowEntry(
            Store(), Runtime(), Checkpoints(), Graph(), temporal_ready
        ).start_or_resume(workspace_id, "agent identity", 20)
    )

    assert persisted.status == "completed"
    assert created is False


def test_workflow_entry_cleans_checkpoints_after_completed_graph_return() -> None:
    workspace_id, run_id = uuid4(), uuid4()
    now = datetime.now(UTC)
    current = ResearchRun(
        id=run_id,
        question="agent identity",
        status="planning",
        status_version=1,
        created_at=now,
        updated_at=now,
    )
    outputs = {
        "summary": "Stored source summary",
        "keywords": ["agentic web"],
        "report": "Stored final report",
        "trust": "eligible",
        "audit": "completed",
    }
    graph_calls = 0
    cleanup_calls: list[Any] = []

    class Store:
        async def get_or_create_run(self, *_):
            return current, False

        async def get_run(self, *_):
            return current

    class Runtime:
        async def ensure_research_assignment(self, *_):
            return None

    class Checkpoints:
        async def readiness(self):
            return CheckpointReadiness(True, 0, "ready")

        def graph_config(self, requested_run_id):
            return ResearchCheckpointLifecycle.graph_config(requested_run_id)

        async def delete_thread(self, requested_run_id):
            cleanup_calls.append((requested_run_id, dict(outputs)))
            return True

    class Graph:
        async def ainvoke(self, *_):
            nonlocal current, graph_calls
            graph_calls += 1
            current = current.model_copy(
                update={"status": "completed", "status_version": 2}
            )

    async def temporal_ready() -> bool:
        return True

    persisted, _created = asyncio.run(
        UnifiedResearchWorkflowEntry(
            Store(), Runtime(), Checkpoints(), Graph(), temporal_ready
        ).start_or_resume(workspace_id, "agent identity", 20)
    )

    assert persisted.status == "completed"
    assert graph_calls == 1
    assert cleanup_calls == [(run_id, outputs)]
    assert outputs == {
        "summary": "Stored source summary",
        "keywords": ["agentic web"],
        "report": "Stored final report",
        "trust": "eligible",
        "audit": "completed",
    }


def test_workflow_entry_keeps_completion_when_checkpoint_cleanup_fails() -> None:
    workspace_id, run_id = uuid4(), uuid4()
    now = datetime.now(UTC)
    current = ResearchRun(
        id=run_id,
        question="agent identity",
        status="planning",
        status_version=1,
        created_at=now,
        updated_at=now,
    )
    cleanup_calls: list[Any] = []

    class Store:
        async def get_or_create_run(self, *_):
            return current, False

        async def get_run(self, *_):
            return current

    class Runtime:
        async def ensure_research_assignment(self, *_):
            return None

    class Checkpoints:
        async def readiness(self):
            return CheckpointReadiness(True, 0, "ready")

        def graph_config(self, requested_run_id):
            return ResearchCheckpointLifecycle.graph_config(requested_run_id)

        async def delete_thread(self, requested_run_id):
            cleanup_calls.append(requested_run_id)
            return False

    class Graph:
        async def ainvoke(self, *_):
            nonlocal current
            current = current.model_copy(
                update={"status": "completed", "status_version": 2}
            )

    async def temporal_ready() -> bool:
        return True

    persisted, _created = asyncio.run(
        UnifiedResearchWorkflowEntry(
            Store(), Runtime(), Checkpoints(), Graph(), temporal_ready
        ).start_or_resume(workspace_id, "agent identity", 20)
    )

    assert persisted.status == "completed"
    assert cleanup_calls == [run_id]


def test_workflow_entry_retries_from_stored_failed_stage() -> None:
    workspace_id, run_id = uuid4(), uuid4()
    now = datetime.now(UTC)
    failed = ResearchRun(
        id=run_id,
        question="agent identity",
        status="failed",
        status_version=4,
        failed_stage="discovering",
        created_at=now,
        updated_at=now,
    )
    resumed = failed.model_copy(
        update={"status": "discovering", "status_version": 5, "failed_stage": None}
    )
    current = failed
    graph_states: list[dict] = []

    class Store:
        async def get_or_create_run(self, *_):
            return current, False

        async def transition_status(self, *args, **_kwargs):
            nonlocal current
            assert args[1:4] == ("failed", 4, "discovering")
            current = resumed
            return True

        async def get_run(self, *_):
            return current

    class Runtime:
        async def ensure_research_assignment(self, *_):
            return None

    class Checkpoints:
        async def readiness(self):
            return CheckpointReadiness(True, 0, "ready")

        def graph_config(self, requested_run_id):
            return ResearchCheckpointLifecycle.graph_config(requested_run_id)

    class Graph:
        async def ainvoke(self, state, _config):
            graph_states.append(state)
            return state

    async def temporal_ready() -> bool:
        return True

    asyncio.run(
        UnifiedResearchWorkflowEntry(
            Store(), Runtime(), Checkpoints(), Graph(), temporal_ready
        ).start_or_resume(workspace_id, "agent identity", 20)
    )

    assert graph_states[0]["canonical_status"] == "discovering"
    assert graph_states[0]["status_version"] == 5


def test_workflow_entry_resumes_exact_waiting_review_thread() -> None:
    workspace_id, run_id = uuid4(), uuid4()
    now = datetime.now(UTC)
    run = ResearchRun(
        id=run_id,
        question="agent identity",
        status="awaiting_review",
        status_version=4,
        created_at=now,
        updated_at=now,
    )
    graph_calls: list[tuple[object, object]] = []

    class Store:
        async def get_run(self, *_):
            return run

    class Checkpoints:
        async def readiness(self):
            return CheckpointReadiness(True, 0, "ready")

        def graph_config(self, requested_run_id):
            return ResearchCheckpointLifecycle.graph_config(requested_run_id)

    class Graph:
        async def ainvoke(self, command, config):
            graph_calls.append((command, config))

    async def temporal_ready() -> bool:
        return True

    resumed = asyncio.run(
        UnifiedResearchWorkflowEntry(
            Store(), object(), Checkpoints(), Graph(), temporal_ready
        ).resume_after_review(
            workspace_id,
            run_id,
            "https://example.com/review",
            "sha256:review",
        )
    )

    assert resumed == run
    assert len(graph_calls) == 1
    assert graph_calls[0][1] == ResearchCheckpointLifecycle.graph_config(run_id)
    assert graph_calls[0][0].resume == {
        "source_url": "https://example.com/review",
        "content_hash": "sha256:review",
        "outcome": "accepted",
    }


def test_workflow_entry_resumes_rejected_review_decision() -> None:
    workspace_id, run_id = uuid4(), uuid4()
    now = datetime.now(UTC)
    run = ResearchRun(
        id=run_id,
        question="agent identity",
        status="awaiting_review",
        status_version=4,
        created_at=now,
        updated_at=now,
    )
    graph_calls: list[tuple[object, object]] = []

    class Store:
        async def get_run(self, *_):
            return run

    class Checkpoints:
        async def readiness(self):
            return CheckpointReadiness(True, 0, "ready")

        def graph_config(self, requested_run_id):
            return ResearchCheckpointLifecycle.graph_config(requested_run_id)

    class Graph:
        async def ainvoke(self, command, config):
            graph_calls.append((command, config))

    async def temporal_ready() -> bool:
        return True

    resumed = asyncio.run(
        UnifiedResearchWorkflowEntry(
            Store(), object(), Checkpoints(), Graph(), temporal_ready
        ).resume_after_review(
            workspace_id,
            run_id,
            "https://example.com/review",
            "sha256:review",
            "rejected",
        )
    )

    assert resumed == run
    assert len(graph_calls) == 1
    assert graph_calls[0][0].resume == {
        "source_url": "https://example.com/review",
        "content_hash": "sha256:review",
        "outcome": "rejected",
    }


def test_canonical_node_uses_database_status_instead_of_checkpoint_status() -> None:
    workflow_state = initial_state()
    workflow_state["canonical_status"] = "reporting"
    workflow_state["status_version"] = 99
    now = datetime.now(UTC)
    current = ResearchRun(
        id=workflow_state["run_id"],
        question=workflow_state["question"],
        status="planning",
        status_version=0,
        created_at=now,
        updated_at=now,
    )
    transitions: list[tuple] = []

    class Store:
        async def get_run(self, *_):
            return current

        async def transition_status(self, *args, **kwargs):
            nonlocal current
            transitions.append((args, kwargs))
            current = current.model_copy(
                update={"status": args[3], "status_version": current.status_version + 1}
            )
            return True

    visited: list[str] = []
    governed = CanonicalResearchWorkflowNodes(
        nodes(visited, coverage={"stage": "coverage_complete"}), Store()
    ).wrapped()

    update = asyncio.run(governed.plan_topics(workflow_state))

    assert transitions[0][0][1:4] == ("planning", 0, "discovering")
    assert update["canonical_status"] == "discovering"
    assert update["status_version"] == 1


def test_local_model_dependency_failure_records_safe_retryable_status() -> None:
    workflow_state = initial_state()
    now = datetime.now(UTC)
    current = ResearchRun(
        id=workflow_state["run_id"],
        question=workflow_state["question"],
        status="planning",
        status_version=0,
        created_at=now,
        updated_at=now,
    )

    class Store:
        async def get_run(self, *_):
            return current

        async def transition_status(self, *args, **kwargs):
            nonlocal current
            assert args[1:4] == ("planning", 0, "failed")
            assert kwargs["failure_code"] == "plan_topics_unavailable"
            assert kwargs["retryable"] is True
            current = current.model_copy(
                update={
                    "status": "failed",
                    "status_version": 1,
                    "failed_stage": "planning",
                    "failure_code": kwargs["failure_code"],
                    "failure_explanation": kwargs["failure_explanation"],
                    "retryable": True,
                }
            )
            return True

    workflow_nodes = nodes(
        [], coverage={"stage": "coverage_complete", "uncovered_topic_ids": []}
    )

    async def unavailable(_: ResearchWorkflowState) -> ResearchWorkflowState:
        raise TopicPlanningUnavailable("model offline")

    workflow_nodes.plan_topics = unavailable
    governed = CanonicalResearchWorkflowNodes(workflow_nodes, Store()).wrapped()

    with pytest.raises(ResearchWorkflowUnavailable, match="temporarily unavailable"):
        asyncio.run(governed.plan_topics(workflow_state))

    assert current.status == "failed"
    assert current.failed_stage == "planning"


def test_canonical_node_fails_safely_on_concurrent_status_change() -> None:
    workflow_state = initial_state()
    now = datetime.now(UTC)
    current = ResearchRun(
        id=workflow_state["run_id"],
        question=workflow_state["question"],
        status="planning",
        status_version=0,
        created_at=now,
        updated_at=now,
    )

    class Store:
        async def get_run(self, *_):
            return current

        async def transition_status(self, *_args, **_kwargs):
            nonlocal current
            current = current.model_copy(
                update={"status": "failed", "status_version": 1}
            )
            return False

    governed = CanonicalResearchWorkflowNodes(
        nodes([], coverage={"stage": "coverage_complete"}), Store()
    ).wrapped()

    with pytest.raises(ResearchWorkflowConflict, match="Official research status"):
        asyncio.run(governed.plan_topics(workflow_state))


def test_resumed_node_records_required_intermediate_status() -> None:
    workflow_state = initial_state()
    now = datetime.now(UTC)
    current = ResearchRun(
        id=workflow_state["run_id"],
        question=workflow_state["question"],
        status="acquiring",
        status_version=2,
        created_at=now,
        updated_at=now,
    )
    transitions: list[tuple[str, str]] = []

    class Store:
        async def get_run(self, *_):
            return current

        async def transition_status(self, *args, **_kwargs):
            nonlocal current
            transitions.append((args[1], args[3]))
            current = current.model_copy(
                update={"status": args[3], "status_version": current.status_version + 1}
            )
            return True

    governed = CanonicalResearchWorkflowNodes(
        nodes([], coverage={"stage": "coverage_complete"}), Store()
    ).wrapped()

    update = asyncio.run(governed.evaluate_relevance(workflow_state))

    assert transitions == [
        ("acquiring", "evaluating_relevance"),
        ("evaluating_relevance", "summarizing"),
    ]
    assert update["canonical_status"] == "summarizing"


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
    workflow_nodes = nodes(
        visited,
        coverage={"stage": "coverage_complete", "uncovered_topic_ids": []},
    )
    relevance_calls = 0

    async def relevance(_: ResearchWorkflowState) -> ResearchWorkflowState:
        nonlocal relevance_calls
        relevance_calls += 1
        visited.append("evaluate_relevance")
        if relevance_calls == 1:
            return {
                "stage": "awaiting_review",
                "review_required_sources": [
                    {
                        "source_url": "https://example.com/review",
                        "content_hash": "sha256:review",
                    }
                ],
            }
        return {"stage": "relevance_decided"}

    workflow_nodes.evaluate_relevance = relevance
    workflow = build_research_workflow(workflow_nodes).compile(
        checkpointer=InMemorySaver()
    )
    workflow_state = initial_state()
    config = ResearchCheckpointLifecycle.graph_config(workflow_state["run_id"])

    result = asyncio.run(workflow.ainvoke(workflow_state, config))

    assert result["stage"] == "awaiting_review"
    review_wait = result["__interrupt__"][0].value
    assert review_wait["wait_type"] == "human_review"
    assert review_wait["evidence_versions"] == [
        {
            "source_url": "https://example.com/review",
            "content_hash": "sha256:review",
        }
    ]
    assert "generate_final_report" not in visited
    assert "complete_research" not in visited

    resumed = asyncio.run(
        workflow.ainvoke(Command(resume={"outcome": "accepted"}), config)
    )

    assert resumed["stage"] == "completed"
    assert relevance_calls == 2


def test_rejected_review_source_does_not_clear_unresolved_review_sources() -> None:
    workspace_id, run_id = uuid4(), uuid4()
    now = datetime.now(UTC)
    run = ResearchRun(
        id=run_id,
        question="agent identity",
        status="evaluating_relevance",
        status_version=4,
        created_at=now,
        updated_at=now,
        sources=[
            SourceCandidate(
                rank=1,
                title="Rejected",
                url="https://example.com/rejected",
                snippet="",
                preflight_status="review_required",
                preflight_content_hash="sha256:rejected",
            ),
            SourceCandidate(
                rank=2,
                title="Still waiting",
                url="https://example.com/waiting",
                snippet="",
                preflight_status="review_required",
                preflight_content_hash="sha256:waiting",
            ),
        ],
    )

    class ResearchStore:
        async def get_run(self, *_: object) -> ResearchRun:
            return run

    class AgenticStore:
        async def list_discovered_sources(self, *_: object) -> list[TopicSourceAssociation]:
            return [
                TopicSourceAssociation(
                    topic_id="agent-identity",
                    source_url="https://example.com/rejected",
                    result_rank=1,
                ),
                TopicSourceAssociation(
                    topic_id="agent-identity",
                    source_url="https://example.com/waiting",
                    result_rank=2,
                ),
            ]

    class TrustService:
        async def list_for_run(self, *_: object) -> list[EvidenceTrustEvaluation]:
            return [
                EvidenceTrustEvaluation(
                    id=uuid4(),
                    run_id=run_id,
                    source_url="https://example.com/rejected",
                    content_hash="sha256:rejected",
                    policy_version="local-default-v2",
                    disposition="review_required",
                    base_disposition="review_required",
                    rule_outcomes=[
                        TrustRuleOutcome(
                            rule="content_type",
                            outcome="review_required",
                            detail="Review.",
                        )
                    ],
                    component_version="web-trust-v2",
                    created_at=now,
                    override_id=uuid4(),
                    override_outcome="rejected",
                    override_actor_user_id=uuid4(),
                    override_created_at=now,
                )
            ]

    class RelevanceService:
        called = False

        async def evaluate(self, *_: object) -> object:
            self.called = True
            return SimpleNamespace(decision="relevant")

    relevance = RelevanceService()
    state = initial_state()
    state["workspace_id"] = workspace_id
    state["run_id"] = run_id
    result = asyncio.run(
        topic_relevance_node(
            ResearchStore(),
            AgenticStore(),
            relevance,
            TrustService(),
        )(state)
    )

    assert result["stage"] == "awaiting_review"
    assert result["review_required_sources"] == [
        {
            "source_url": "https://example.com/waiting",
            "content_hash": "sha256:waiting",
        }
    ]
    assert relevance.called is False


def test_durable_interrupt_resumes_same_checkpointed_thread() -> None:
    visited: list[str] = []
    workflow = build_research_workflow(
        nodes(
            visited,
            acquisition={"stage": "awaiting_preflight"},
            coverage={"stage": "coverage_complete", "uncovered_topic_ids": []},
        )
    ).compile(checkpointer=InMemorySaver())
    workflow_state = initial_state()
    config = ResearchCheckpointLifecycle.graph_config(workflow_state["run_id"])

    interrupted = asyncio.run(workflow.ainvoke(workflow_state, config))

    assert interrupted["stage"] == "awaiting_preflight"
    assert interrupted["__interrupt__"][0].value["wait_type"] == "candidate_preflight"
    resumed = asyncio.run(workflow.ainvoke(Command(resume={"status": "completed"}), config))
    assert resumed["stage"] == "completed"
    assert visited.count("plan_topics") == 1
    assert visited.count("evaluate_relevance") == 1


def test_failed_durable_result_routes_to_graph_owned_failure_node() -> None:
    visited: list[str] = []
    workflow = build_research_workflow(
        nodes(
            visited,
            acquisition={"stage": "awaiting_preflight"},
            coverage={"stage": "coverage_complete", "uncovered_topic_ids": []},
        )
    ).compile(checkpointer=InMemorySaver())
    workflow_state = initial_state()
    config = ResearchCheckpointLifecycle.graph_config(workflow_state["run_id"])

    asyncio.run(workflow.ainvoke(workflow_state, config))
    result = asyncio.run(workflow.ainvoke(Command(resume={"outcome": "failed"}), config))

    assert result["stage"] == "failed"
    assert result["failure_code"] == "durable_work_failed"
    assert result["retryable"] is True
    assert "fail_durable_work" in visited
    assert "evaluate_relevance" not in visited


def test_failed_summary_work_reports_no_usable_summaries() -> None:
    visited: list[str] = []
    workflow = build_research_workflow(
        nodes(
            visited,
            summary={"stage": "awaiting_summaries"},
            coverage={"stage": "coverage_complete", "uncovered_topic_ids": []},
        )
    ).compile(checkpointer=InMemorySaver())
    workflow_state = initial_state()
    config = ResearchCheckpointLifecycle.graph_config(workflow_state["run_id"])

    asyncio.run(workflow.ainvoke(workflow_state, config))
    result = asyncio.run(workflow.ainvoke(Command(resume={"outcome": "failed"}), config))

    assert result["stage"] == "failed"
    assert result["failure_code"] == "summary_work_no_usable_summaries"
    assert result["failure_explanation"] == (
        "Summary processing completed without any usable source summaries."
    )
    assert result["retryable"] is True
    assert "fail_durable_work" in visited
    assert "assess_topic_coverage" not in visited
