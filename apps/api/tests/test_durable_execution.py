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
