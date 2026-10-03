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
            continuation = (
                request.continuation
                if result == "completed"
                else WorkflowContinuationEnvelope(
                    wait=request.continuation.wait,
                    result_record_id=request.continuation.result_record_id,
                    outcome="failed",
                )
            )
        except ActivityError:
            result = "failed"
            await workflow.execute_activity(
                "fail_evidence_summary_execution",
                request.execution_id,
                start_to_close_timeout=timedelta(minutes=2),
                retry_policy=RetryPolicy(maximum_attempts=3),
            )
            continuation = WorkflowContinuationEnvelope(
                wait=request.continuation.wait,
                result_record_id=request.continuation.result_record_id,
                outcome="failed",
            )
        work_set_status = await workflow.execute_activity(
            "complete_evidence_summary_work_set",
            request.execution_id,
            start_to_close_timeout=timedelta(minutes=2),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )
        if work_set_status == "waiting":
            return result
        if work_set_status == "completed":
            continuation = request.continuation
        elif work_set_status == "failed":
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
