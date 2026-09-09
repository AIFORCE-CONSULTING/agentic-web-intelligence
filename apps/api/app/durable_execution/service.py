"""Server-only Temporal scheduling boundary for approved runtime runs."""

from temporalio.client import Client

from app.agent_runtime.contracts import RuntimeRun
from app.durable_execution.contracts import RuntimeExecutionEnvelope
from app.durable_execution.workflows import GovernedRuntimeWorkflow

POLICY_VERSION = "phase-5-v1"


class DurableExecutionUnavailable(RuntimeError):
    """Raised when durable execution is not configured or reachable."""


class DurableExecutionPolicyError(ValueError):
    """Raised when a stored run is not eligible for durable scheduling."""


class TemporalRuntimeBoundary:
    """Start one fixed workflow only after the runtime has approved its plan.

    This class is deliberately neither an HTTP route nor an MCP tool. It is
    used only by trusted server-side orchestration code.
    """

    def __init__(self, address: str | None, namespace: str, task_queue: str) -> None:
        self._address = address
        self._namespace = namespace
        self._task_queue = task_queue

    @property
    def configured(self) -> bool:
        return bool(self._address)

    async def schedule_approved_run(self, run: RuntimeRun) -> RuntimeExecutionEnvelope:
        """Schedule a fixed workflow for an existing approval-gated run only."""

        if not self._address:
            raise DurableExecutionUnavailable("Durable execution is not configured.")
        if run.status != "awaiting_approval" or run.workspace_id is None:
            raise DurableExecutionPolicyError(
                "Only a workspace-owned runtime run awaiting approved execution may be scheduled."
            )
        if not any(event.event_type == "runtime.approval.approved" for event in run.events):
            raise DurableExecutionPolicyError(
                "Only a runtime run with recorded human approval may be scheduled."
            )
        envelope = RuntimeExecutionEnvelope(
            run_id=str(run.id), workspace_id=str(run.workspace_id), policy_version=POLICY_VERSION
        )
        client = await Client.connect(self._address, namespace=self._namespace)
        await client.start_workflow(
            GovernedRuntimeWorkflow.run,
            envelope,
            id=f"runtime-{run.id}",
            task_queue=self._task_queue,
        )
        return envelope

    async def cancel_scheduled_run(self, run_id: str) -> None:
        """Request cancellation of one known workflow ID; never accept arbitrary names."""

        if not self._address:
            raise DurableExecutionUnavailable("Durable execution is not configured.")
        client = await Client.connect(self._address, namespace=self._namespace)
        await client.get_workflow_handle(f"runtime-{run_id}").cancel()
