"""Fixed Temporal workflow for durable local evidence summary work."""

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy


@workflow.defn
class EvidenceSummaryWorkflow:
    """Process only one pre-existing, server-owned execution identifier."""

    @workflow.run
    async def run(self, execution_id: str) -> str:
        return await workflow.execute_activity(
            "execute_evidence_summary",
            execution_id,
            start_to_close_timeout=timedelta(minutes=20),
            retry_policy=RetryPolicy(maximum_attempts=1),
        )
