"""Deterministic Temporal workflow for one already-approved runtime plan."""

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

from app.durable_execution.contracts import DurableExecutionResult, RuntimeExecutionEnvelope


@workflow.defn
class GovernedRuntimeWorkflow:
    """Pause for a fixed human decision, then run the fixed executor/reviewer loop."""

    def __init__(self) -> None:
        # A signal is merely a durable notification. It cannot carry a goal,
        # capability, workflow name, or other authority-bearing input.
        self._approval_decision: str | None = None

    @workflow.signal
    def approve_execution(self) -> None:
        """Accept the one pre-defined execution path after API authorization."""

        if self._approval_decision is None:
            self._approval_decision = "approved"

    @workflow.signal
    def reject_execution(self) -> None:
        """End the workflow after API code has recorded the rejection."""

        if self._approval_decision is None:
            self._approval_decision = "rejected"

    @workflow.run
    async def run(self, envelope: RuntimeExecutionEnvelope) -> DurableExecutionResult:
        """Wait without consuming a worker, then invoke fixed validated activities."""

        await workflow.wait_condition(lambda: self._approval_decision is not None)
        if self._approval_decision == "rejected":
            return DurableExecutionResult(run_id=envelope.run_id, status="rejected")

        for _ in range(2):
            status = await workflow.execute_activity(
                "execute_approved_runtime_run",
                envelope,
                start_to_close_timeout=timedelta(minutes=6),
                retry_policy=RetryPolicy(maximum_attempts=1),
            )
            if status != "reviewing":
                return DurableExecutionResult(run_id=envelope.run_id, status=status)
            status = await workflow.execute_activity(
                "review_approved_runtime_run",
                envelope,
                start_to_close_timeout=timedelta(minutes=3),
                retry_policy=RetryPolicy(maximum_attempts=1),
            )
            if status != "executing":
                return DurableExecutionResult(run_id=envelope.run_id, status=status)
        return DurableExecutionResult(run_id=envelope.run_id, status="needs_attention")
