"""Fixed Temporal workflow for server-owned candidate preflight."""

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy


@workflow.defn
class CandidatePreflightWorkflow:
    """Run a pre-existing research run's pending candidates without caller-provided URLs."""

    @workflow.run
    async def run(self, run_id: str) -> str:
        return await workflow.execute_activity(
            "preflight_source_candidates",
            run_id,
            start_to_close_timeout=timedelta(minutes=15),
            retry_policy=RetryPolicy(maximum_attempts=1),
        )
