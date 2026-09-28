"""Fixed Temporal workflow for server-owned candidate preflight."""

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError

from app.durable_execution.contracts import (
    CandidatePreflightWorkflowInput,
    WorkflowContinuationEnvelope,
)


@workflow.defn
class CandidatePreflightWorkflow:
    """Run the platform-selected, stored candidate batch for one discovery event."""

    @workflow.run
    async def run(self, request: CandidatePreflightWorkflowInput) -> str:
        try:
            result = await workflow.execute_activity(
                "preflight_source_candidates",
                request.request_json,
                start_to_close_timeout=timedelta(minutes=15),
                retry_policy=RetryPolicy(maximum_attempts=1),
            )
            continuation = request.continuation
        except ActivityError:
            result = "failed"
            continuation = WorkflowContinuationEnvelope(
                wait=request.continuation.wait,
                result_record_id=request.continuation.result_record_id,
                outcome="failed",
            )
        await workflow.execute_activity(
            "continue_unified_research",
            continuation,
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )
        return result
