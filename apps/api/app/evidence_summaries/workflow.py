"""Fixed Temporal workflow for durable local evidence summary work."""

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError

from app.durable_execution.contracts import (
    EvidenceSummaryWorkflowInput,
    WorkflowContinuationEnvelope,
)


@workflow.defn
class EvidenceSummaryWorkflow:
    """Process only one pre-existing, server-owned execution identifier."""

    @workflow.run
    async def run(self, request: EvidenceSummaryWorkflowInput) -> str:
        try:
            result = await workflow.execute_activity(
                "execute_evidence_summary",
                request.execution_id,
                start_to_close_timeout=timedelta(minutes=20),
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
