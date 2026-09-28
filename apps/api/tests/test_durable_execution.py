"""Contract tests for the server-only durable execution boundary."""

import asyncio
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.agent_runtime.research_workflow import (
    ResearchWorkflowContinuation,
    ResearchWorkflowUnavailable,
)
from app.durable_execution.contracts import (
    CandidatePreflightWorkflowInput,
    DurableWait,
    EvidenceSummaryWorkflowInput,
    WorkflowContinuationEnvelope,
    WorkflowThreadReference,
)
from app.evidence_summaries.workflow import EvidenceSummaryWorkflow
from app.identity.authorization import AuthorizationError, require_permission
from app.identity.contracts import AuthenticatedUser
from app.web_research.contracts import ResearchRun
from app.web_trust.workflow import CandidatePreflightWorkflow


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
