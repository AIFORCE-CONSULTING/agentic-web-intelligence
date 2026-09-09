"""Dedicated durable worker; it contains no browser, identity, or connector secrets."""

import asyncio
from uuid import UUID

from temporalio import activity
from temporalio.client import Client
from temporalio.worker import Worker

from app.agent_runtime.service import RuntimeService
from app.agent_runtime.store import RuntimeStore
from app.agent_runtime.workflow import run_deterministic_executor, run_deterministic_reviewer
from app.durable_execution.contracts import RuntimeExecutionEnvelope
from app.durable_execution.workflows import GovernedRuntimeWorkflow
from app.secrets import DeploymentSecrets
from app.settings import get_settings
from app.web_research.mcp_host import GovernedWebMcpHost


def _runtime_dependencies() -> tuple[RuntimeService, GovernedWebMcpHost]:
    settings = get_settings()
    settings.validate_runtime_configuration()
    if not settings.database_url:
        raise RuntimeError("The durable worker requires DATABASE_URL.")
    secrets = DeploymentSecrets(settings)
    return (
        RuntimeService(RuntimeStore(settings.database_url, secrets.redact)),
        GovernedWebMcpHost(deployment_secrets=secrets),
    )


async def _validated_run(service: RuntimeService, envelope: RuntimeExecutionEnvelope):
    run = await service.get_run(UUID(envelope.run_id))
    if str(run.workspace_id) != envelope.workspace_id:
        raise RuntimeError("Durable execution envelope workspace does not match the stored run.")
    return run


@activity.defn(name="execute_approved_runtime_run")
async def execute_approved_runtime_run(envelope: RuntimeExecutionEnvelope) -> str:
    """Execute only the stored, approval-gated researcher step."""

    service, host = _runtime_dependencies()
    run = await _validated_run(service, envelope)
    if run.status not in {"awaiting_approval", "executing"}:
        raise RuntimeError("Stored run is not eligible for durable researcher execution.")
    return (await run_deterministic_executor(service, host, envelope.run_id)).status


@activity.defn(name="review_approved_runtime_run")
async def review_approved_runtime_run(envelope: RuntimeExecutionEnvelope) -> str:
    """Run the existing no-tool reviewer against the stored run only."""

    service, _ = _runtime_dependencies()
    run = await _validated_run(service, envelope)
    if run.status != "reviewing":
        raise RuntimeError("Stored run is not eligible for durable review.")
    return (await run_deterministic_reviewer(service, envelope.run_id)).status


async def run_worker() -> None:
    """Connect the dedicated worker to its one configured task queue."""

    settings = get_settings()
    settings.validate_runtime_configuration()
    if not settings.temporal_address:
        raise RuntimeError("The durable worker requires TEMPORAL_ADDRESS.")
    client = await Client.connect(settings.temporal_address, namespace=settings.temporal_namespace)
    worker = Worker(
        client,
        task_queue=settings.temporal_task_queue,
        workflows=[GovernedRuntimeWorkflow],
        activities=[execute_approved_runtime_run, review_approved_runtime_run],
    )
    await worker.run()


if __name__ == "__main__":
    asyncio.run(run_worker())
