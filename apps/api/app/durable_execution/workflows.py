"""Deterministic Temporal workflow for one durable, already-approved runtime plan."""

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

from app.agent_runtime.policy import MAX_RESEARCH_ATTEMPTS
from app.durable_execution.contracts import DurableExecutionResult, RuntimeExecutionEnvelope


@workflow.defn
class GovernedRuntimeWorkflow:
    """Run fixed activities only after runtime-owned approval has already occurred."""

    @workflow.run
    async def run(self, envelope: RuntimeExecutionEnvelope) -> DurableExecutionResult:
        """Invoke fixed validated activities; Temporal does not own approval state."""

        try:
            # This is the fixed, policy-owned initial pass plus its two
            # routine reviewer-to-researcher revisions. Operator exceptions
            # are separate runtime decisions and require a later schedule.
            for _ in range(MAX_RESEARCH_ATTEMPTS):
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
        except Exception:
            status = await workflow.execute_activity(
                "escalate_durable_execution",
                envelope,
                start_to_close_timeout=timedelta(minutes=1),
                retry_policy=RetryPolicy(maximum_attempts=1),
            )
            return DurableExecutionResult(run_id=envelope.run_id, status=status)
        return DurableExecutionResult(run_id=envelope.run_id, status="needs_attention")
