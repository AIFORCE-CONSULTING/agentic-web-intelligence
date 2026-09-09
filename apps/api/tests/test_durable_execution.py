"""Contract tests for the server-only durable execution boundary."""

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.agent_runtime.contracts import RuntimeRun
from app.durable_execution.service import (
    DurableExecutionPolicyError,
    DurableExecutionUnavailable,
    TemporalRuntimeBoundary,
)
from app.identity.authorization import AuthorizationError, require_permission
from app.identity.contracts import AuthenticatedUser


def _run(status: str = "awaiting_approval", workspace_id=None) -> RuntimeRun:
    now = datetime.now(UTC)
    return RuntimeRun(
        id=uuid4(),
        goal="Research a topic",
        status=status,
        workspace_id=workspace_id or uuid4(),
        created_at=now,
        updated_at=now,
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
