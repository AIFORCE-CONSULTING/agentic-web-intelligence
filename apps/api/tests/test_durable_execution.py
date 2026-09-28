"""Contract tests for the server-only durable execution boundary."""

import asyncio
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.agent_runtime.contracts import RuntimeEvent, RuntimeRun
from app.agent_runtime.research_workflow import (
    ResearchWorkflowContinuation,
    ResearchWorkflowUnavailable,
)
from app.durable_execution.contracts import (
    CandidatePreflightWorkflowInput,
    DurableWait,
    EvidenceSummaryWorkflowInput,
    RuntimeExecutionEnvelope,
    WorkflowContinuationEnvelope,
    WorkflowThreadReference,
)
from app.durable_execution.service import (
    DurableExecutionPolicyError,
    DurableExecutionUnavailable,
    TemporalRuntimeBoundary,
)
from app.durable_execution.worker import _validated_run, execute_approved_runtime_run
from app.durable_execution.workflows import GovernedRuntimeWorkflow
from app.evidence_summaries.workflow import EvidenceSummaryWorkflow
from app.identity.authorization import AuthorizationError, require_permission
from app.identity.contracts import AuthenticatedUser
from app.web_research.contracts import ResearchRun
from app.web_trust.workflow import CandidatePreflightWorkflow


def _run(status: str = "awaiting_approval", workspace_id=None) -> RuntimeRun:
    now = datetime.now(UTC)
    return RuntimeRun(
        id=uuid4(),
        goal="Research a topic",
        status=status,
        workspace_id=workspace_id or uuid4(),
        created_at=now,
        updated_at=now,
        events=[RuntimeEvent(event_type="runtime.approval.approved", occurred_at=now)],
    )


def test_temporal_boundary_never_schedules_an_unapproved_or_unowned_run() -> None:
    boundary = TemporalRuntimeBoundary("temporal:7233", "default", "platform-runtime-v1")

    with pytest.raises(DurableExecutionPolicyError, match="awaiting approved"):
        asyncio.run(boundary.schedule_approved_run(_run("planning")))
    with pytest.raises(DurableExecutionPolicyError, match="workspace-owned"):
        asyncio.run(
            boundary.schedule_approved_run(_run().model_copy(update={"workspace_id": None}))
        )


def test_temporal_boundary_requires_explicit_configuration() -> None:
    boundary = TemporalRuntimeBoundary(None, "default", "platform-runtime-v1")
    with pytest.raises(DurableExecutionUnavailable, match="not configured"):
        asyncio.run(boundary.schedule_approved_run(_run()))


def test_temporal_boundary_starts_only_the_fixed_runtime_workflow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[object, object, dict[str, object]]] = []

    class FakeClient:
        async def start_workflow(self, workflow, envelope, **kwargs):
            calls.append((workflow, envelope, kwargs))

    async def connect(address: str, namespace: str) -> FakeClient:
        assert address == "temporal:7233"
        assert namespace == "default"
        return FakeClient()

    monkeypatch.setattr("app.durable_execution.service.Client.connect", connect)
    run = _run()
    boundary = TemporalRuntimeBoundary("temporal:7233", "default", "platform-runtime-v1")
    envelope = asyncio.run(
        boundary.schedule_approved_run(run)
    )

    assert envelope.run_id == str(run.id)
    assert envelope.workspace_id == str(run.workspace_id)
    assert len(calls) == 1
    assert calls[0][2]["id"] == f"runtime-{run.id}"
    assert calls[0][2]["task_queue"] == "platform-runtime-v1"


def test_temporal_boundary_cancels_only_the_server_derived_workflow_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cancelled: list[str] = []

    class FakeHandle:
        async def cancel(self) -> None:
            cancelled.append("cancelled")

    class FakeClient:
        def get_workflow_handle(self, workflow_id: str) -> FakeHandle:
            assert workflow_id == "runtime-run-123"
            return FakeHandle()

    async def connect(_: str, namespace: str) -> FakeClient:
        assert namespace == "default"
        return FakeClient()

    monkeypatch.setattr("app.durable_execution.service.Client.connect", connect)
    boundary = TemporalRuntimeBoundary("temporal:7233", "default", "platform-runtime-v1")
    asyncio.run(boundary.cancel_scheduled_run("run-123"))

    assert cancelled == ["cancelled"]


def test_temporal_boundary_requires_runtime_owned_human_approval() -> None:
    boundary = TemporalRuntimeBoundary("temporal:7233", "default", "platform-runtime-v1")

    with pytest.raises(DurableExecutionPolicyError, match="recorded human approval"):
        asyncio.run(boundary.schedule_approved_run(_run().model_copy(update={"events": []})))


def test_runtime_execution_permission_excludes_viewers() -> None:
    viewer = AuthenticatedUser(
        id=uuid4(),
        email="viewer@example.com",
        workspace_id=uuid4(),
        workspace_name="Viewer workspace",
        role="viewer",
        authenticated_at=datetime.now(UTC),
    )
    with pytest.raises(AuthorizationError, match="not permitted"):
        require_permission(viewer, "runtime.execute")


def test_worker_revalidates_workspace_and_policy_on_each_recovery() -> None:
    run = _run()

    class FakeService:
        async def get_run(self, _: object) -> RuntimeRun:
            return run

    envelope = RuntimeExecutionEnvelope(
        run_id=str(run.id), workspace_id=str(run.workspace_id), policy_version="phase-5-v1"
    )
    recovered_once = asyncio.run(_validated_run(FakeService(), envelope))
    recovered_twice = asyncio.run(_validated_run(FakeService(), envelope))

    assert recovered_once.id == run.id
    assert recovered_twice.id == run.id

    with pytest.raises(RuntimeError, match="workspace"):
        asyncio.run(
            _validated_run(
                FakeService(),
                envelope.__class__(
                    run_id=envelope.run_id,
                    workspace_id=str(uuid4()),
                    policy_version=envelope.policy_version,
                ),
            )
        )
    with pytest.raises(RuntimeError, match="policy version"):
        asyncio.run(
            _validated_run(
                FakeService(),
                envelope.__class__(
                    run_id=envelope.run_id,
                    workspace_id=envelope.workspace_id,
                    policy_version="retired-policy",
                ),
            )
        )


def test_cancelled_run_returns_without_calling_a_research_tool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = _run("cancelled")

    class FakeService:
        async def get_run(self, _: object) -> RuntimeRun:
            return run

    monkeypatch.setattr(
        "app.durable_execution.worker._runtime_dependencies", lambda: (FakeService(), object())
    )
    outcome = asyncio.run(
        execute_approved_runtime_run(
            RuntimeExecutionEnvelope(
                run_id=str(run.id),
                workspace_id=str(run.workspace_id),
                policy_version="phase-5-v1",
            )
        )
    )

    assert outcome == "cancelled"


def test_durable_workflow_runs_only_the_three_policy_owned_routine_attempts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A workflow cannot grow the normal reviewer/researcher loop by itself."""

    envelope = RuntimeExecutionEnvelope(
        run_id=str(uuid4()), workspace_id=str(uuid4()), policy_version="phase-5-v1"
    )
    calls: list[str] = []

    async def execute_activity(name: str, *_: object, **__: object) -> str:
        calls.append(name)
        return "reviewing" if name == "execute_approved_runtime_run" else "executing"

    monkeypatch.setattr(
        "app.durable_execution.workflows.workflow.execute_activity", execute_activity
    )

    result = asyncio.run(GovernedRuntimeWorkflow().run(envelope))

    assert result.status == "needs_attention"
    assert calls == [
        "execute_approved_runtime_run",
        "review_approved_runtime_run",
        "execute_approved_runtime_run",
        "review_approved_runtime_run",
        "execute_approved_runtime_run",
        "review_approved_runtime_run",
    ]


def continuation_envelope(
    *, outcome: str = "completed", status: str = "acquiring", version: int = 2
) -> WorkflowContinuationEnvelope:
    workspace_id, run_id = uuid4(), uuid4()
    return WorkflowContinuationEnvelope(
        wait=DurableWait(
            thread=WorkflowThreadReference(
                research_run_id=str(run_id),
                workspace_id=str(workspace_id),
                thread_id=str(run_id),
            ),
            execution_id="operation-1",
            wait_type="candidate_preflight",
            expected_research_status=status,
            expected_status_version=version,
            idempotency_key=f"continuation:{run_id}:2",
        ),
        result_record_id="operation-1",
        outcome=outcome,
    )


@pytest.mark.parametrize(
    ("workflow_class", "request_factory", "work_activity"),
    [
        (
            CandidatePreflightWorkflow,
            lambda envelope: CandidatePreflightWorkflowInput(
                request_json='{"run_id":"00000000-0000-0000-0000-000000000001",'
                '"source_urls":["https://example.com"]}',
                continuation=envelope,
            ),
            "preflight_source_candidates",
        ),
        (
            EvidenceSummaryWorkflow,
            lambda envelope: EvidenceSummaryWorkflowInput(
                execution_id="operation-1", continuation=envelope
            ),
            "execute_evidence_summary",
        ),
    ],
)
def test_durable_work_stores_result_before_requesting_graph_continuation(
    monkeypatch: pytest.MonkeyPatch,
    workflow_class,
    request_factory,
    work_activity: str,
) -> None:
    calls: list[tuple[str, object]] = []

    async def execute_activity(name: str, argument: object, **_: object) -> str:
        calls.append((name, argument))
        return "completed"

    module = (
        "app.web_trust.workflow.workflow.execute_activity"
        if workflow_class is CandidatePreflightWorkflow
        else "app.evidence_summaries.workflow.workflow.execute_activity"
    )
    monkeypatch.setattr(module, execute_activity)
    envelope = continuation_envelope()

    result = asyncio.run(workflow_class().run(request_factory(envelope)))

    assert result == "completed"
    assert [name for name, _ in calls] == [work_activity, "continue_unified_research"]
    assert calls[1][1] == envelope


def test_continuation_resumes_once_and_ignores_duplicate_completion() -> None:
    envelope = continuation_envelope()
    wait = envelope.wait
    now = datetime.now(UTC)
    run = ResearchRun(
        id=UUID(wait.thread.research_run_id),
        question="agent identity",
        status=wait.expected_research_status,
        status_version=wait.expected_status_version,
        created_at=now,
        updated_at=now,
    )
    claims = 0
    finishes: list[tuple] = []
    graph_calls: list[tuple] = []

    class Store:
        async def get_run(self, *_):
            return run

        async def claim_workflow_continuation(self, *_):
            nonlocal claims
            claims += 1
            return claims == 1

        async def finish_workflow_continuation(self, *args):
            finishes.append(args)

    class Graph:
        async def ainvoke(self, state, config):
            graph_calls.append((state, config))
            return {}

    class Checkpoints:
        @staticmethod
        def graph_config(run_id):
            return {"configurable": {"thread_id": str(run_id)}}

    class Verifier:
        async def verify_result(self, _):
            return True

    service = ResearchWorkflowContinuation(Store(), Graph(), Checkpoints(), Verifier())

    assert asyncio.run(service.continue_after(envelope)) == "completed"
    assert asyncio.run(service.continue_after(envelope)) == "duplicate"
    assert len(graph_calls) == 1
    assert finishes[-1][1] == "completed"


def test_continuation_rejects_stale_status_without_resuming_graph() -> None:
    envelope = continuation_envelope()
    wait = envelope.wait
    now = datetime.now(UTC)
    run = ResearchRun(
        id=UUID(wait.thread.research_run_id),
        question="agent identity",
        status="summarizing",
        status_version=wait.expected_status_version + 1,
        created_at=now,
        updated_at=now,
    )
    finishes: list[tuple] = []

    class Store:
        async def get_run(self, *_):
            return run

        async def claim_workflow_continuation(self, *_):
            return True

        async def finish_workflow_continuation(self, *args):
            finishes.append(args)

    class Graph:
        async def ainvoke(self, *_):
            raise AssertionError("Stale completion must not resume LangGraph.")

    class Verifier:
        async def verify_result(self, _):
            return True

    service = ResearchWorkflowContinuation(Store(), Graph(), object(), Verifier())

    assert asyncio.run(service.continue_after(envelope)) == "stale"
    assert finishes[-1][1] == "stale"


def test_continuation_fails_closed_for_wrong_workspace() -> None:
    envelope = continuation_envelope()

    class Store:
        async def get_run(self, *_):
            return None

    service = ResearchWorkflowContinuation(Store(), object(), object(), object())

    with pytest.raises(ResearchWorkflowUnavailable, match="record is unavailable"):
        asyncio.run(service.continue_after(envelope))
