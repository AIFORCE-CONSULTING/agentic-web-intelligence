"""Fixed Temporal workflow for server-owned candidate preflight."""

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy


@workflow.defn
class CandidatePreflightWorkflow:
    """Run the platform-selected, stored candidate batch for one discovery event."""

    @workflow.run
    async def run(self, request: str) -> str:
        return await workflow.execute_activity(
            "preflight_source_candidates",
            request,
            start_to_close_timeout=timedelta(minutes=15),
            retry_policy=RetryPolicy(maximum_attempts=1),
        )
