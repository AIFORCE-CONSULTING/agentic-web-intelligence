"""Deterministic Temporal workflow for one already-approved runtime plan."""

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

from app.durable_execution.contracts import DurableExecutionResult, RuntimeExecutionEnvelope


@workflow.defn
class GovernedRuntimeWorkflow:
    """Run the existing executor/reviewer loop without creating authority."""

    @workflow.run
    async def run(self, envelope: RuntimeExecutionEnvelope) -> DurableExecutionResult:
        """Invoke fixed activities; each reloads and validates persisted authority."""

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
