"""Dedicated durable worker; it contains no browser, identity, or connector secrets."""

import asyncio
from uuid import UUID

from temporalio import activity
from temporalio.client import Client
from temporalio.worker import Worker

from app.agent_runtime.research_workflow import (
    ResearchCheckpointLifecycle,
    ResearchWorkflowContinuation,
    compile_research_workflow,
)
from app.agent_runtime.service import RuntimeService
from app.agent_runtime.store import RuntimeStore
from app.agentic_research.relevance import TopicRelevanceService
from app.agentic_research.reporting import ResearchReportingService
from app.agentic_research.store import AgenticResearchStore
from app.agentic_research.topic_planning import TopicPlanningService
from app.agentic_research.workflow_nodes import platform_research_nodes
from app.durable_execution.contracts import WorkflowContinuationEnvelope
from app.evidence_summaries.service import (
    EvidenceSummaryAutomation,
    EvidenceSummaryService,
    EvidenceSummaryTemporalBoundary,
)
from app.evidence_summaries.store import EvidenceSummaryStore
from app.evidence_summaries.workflow import EvidenceSummaryWorkflow
from app.local_models.service import LocalModelProviderService
from app.local_models.store import LocalModelProviderStore
from app.secrets import DeploymentSecrets
from app.settings import get_settings
from app.web_research.mcp_host import GovernedWebMcpHost
from app.web_research.store import ResearchStore
from app.web_trust.contracts import CandidatePreflightRequest
from app.web_trust.preflight import (
    CandidatePreflightService,
    CandidatePreflightTemporalBoundary,
)
from app.web_trust.service import EvidenceTrustService
from app.web_trust.store import WebTrustStore
from app.web_trust.workflow import CandidatePreflightWorkflow


class StoredDurableResultVerifier:
    """Verify owning application records without reading Temporal history."""

    def __init__(
        self,
        research_store: ResearchStore,
        summary_store: EvidenceSummaryStore,
    ) -> None:
        self._research_store = research_store
        self._summary_store = summary_store

    async def verify_result(self, envelope: WorkflowContinuationEnvelope) -> bool:
        if envelope.outcome == "failed":
            return True
        wait = envelope.wait
        if wait.wait_type == "evidence_summary":
            work_set = await self._summary_store.refresh_work_set(
                UUID(envelope.result_record_id)
            )
            if work_set is not None:
                return work_set.status in {"completed", "failed"}
            execution = await self._summary_store.get_execution_for_worker(
                UUID(envelope.result_record_id)
            )
            return execution is not None and execution.status == "completed"
        run = await self._research_store.get_run(
            UUID(wait.thread.workspace_id), UUID(wait.thread.research_run_id)
        )
        return run is not None and all(
            source.preflight_status not in {"pending", "checking"}
            for source in run.sources
        )


async def _research_continuation_dependencies():
    """Build the worker's canonical graph from existing platform owners."""

    settings = get_settings()
    settings.validate_runtime_configuration()
    if not settings.database_url:
        raise RuntimeError("The durable worker requires DATABASE_URL.")
    secrets = DeploymentSecrets(settings)
    research_store = ResearchStore(settings.database_url, secrets.redact)
    runtime_service = RuntimeService(
        RuntimeStore(settings.database_url, secrets.redact), research_store
    )
    summary_store = EvidenceSummaryStore(settings.database_url)
    agentic_store = AgenticResearchStore(settings.database_url)
    local_models = LocalModelProviderService(LocalModelProviderStore(settings.database_url))
    trust = EvidenceTrustService(WebTrustStore(settings.database_url, secrets.redact))

    async def correlated_audit(correlation, outcome, details) -> None:
        await research_store.record_mcp_tool_event(
            correlation.workspace_id,
            str(correlation.request_id),
            correlation.tool_name,
            outcome,
            details,
            research_run_id=correlation.research_run_id,
            runtime_run_id=correlation.runtime_run_id,
            runtime_step_id=correlation.runtime_step_id,
            authorization_decision_id=correlation.authorization_decision_id,
            resource_type=correlation.resource_type,
            resource_id=correlation.resource_id,
        )

    mcp = GovernedWebMcpHost(
        correlated_audit_recorder=correlated_audit,
        deployment_secrets=secrets,
    )
    summary_service = EvidenceSummaryService(
        summary_store, research_store, local_models, trust
    )
    summary_temporal = EvidenceSummaryTemporalBoundary(
        settings.temporal_address,
        settings.temporal_namespace,
        settings.temporal_task_queue,
    )
    nodes = platform_research_nodes(
        topic_planning=TopicPlanningService(agentic_store, local_models),
        authority=runtime_service,
        mcp=mcp,
        research_store=research_store,
        agentic_store=agentic_store,
        preflight=CandidatePreflightService(research_store, trust),
        preflight_temporal=CandidatePreflightTemporalBoundary(
            settings.temporal_address,
            settings.temporal_namespace,
            settings.temporal_task_queue,
        ),
        relevance=TopicRelevanceService(agentic_store, local_models),
        trust=trust,
        summaries=EvidenceSummaryAutomation(
            summary_service,
            summary_store,
            research_store,
            summary_temporal,
        ),
        reporting=ResearchReportingService(agentic_store, local_models),
    )
    checkpoints = ResearchCheckpointLifecycle(settings.database_url, research_store)
    saver = await checkpoints.start()
    graph = compile_research_workflow(nodes, research_store, saver)
    continuation = ResearchWorkflowContinuation(
        research_store,
        graph,
        checkpoints,
        StoredDurableResultVerifier(research_store, summary_store),
    )
    return continuation, checkpoints


@activity.defn(name="continue_unified_research")
async def continue_unified_research(envelope: WorkflowContinuationEnvelope) -> str:
    """Resume one verified graph thread without writing research status here."""

    continuation, checkpoints = await _research_continuation_dependencies()
    try:
        return await continuation.continue_after(envelope)
    finally:
        await checkpoints.stop()


@activity.defn(name="execute_evidence_summary")
async def execute_evidence_summary(execution_id: str) -> str:
    """Execute one stored evidence-summary record, with no caller-provided text or tools."""

    settings = get_settings()
    if not settings.database_url:
        raise RuntimeError("The durable worker requires DATABASE_URL.")
    # The research store is deliberately used only to retrieve evidence selected by the record.
    secrets = DeploymentSecrets(settings)
    service = EvidenceSummaryService(
        EvidenceSummaryStore(settings.database_url),
        ResearchStore(settings.database_url, secrets.redact),
        LocalModelProviderService(LocalModelProviderStore(settings.database_url)),
        EvidenceTrustService(WebTrustStore(settings.database_url, secrets.redact)),
    )
    return (await service.execute(UUID(execution_id))).status


@activity.defn(name="fail_evidence_summary_execution")
async def fail_evidence_summary_execution(execution_id: str) -> None:
    """Make a crashed durable job terminal before aggregate progress is evaluated."""

    settings = get_settings()
    if not settings.database_url:
        raise RuntimeError("The durable worker requires DATABASE_URL.")
    await EvidenceSummaryStore(settings.database_url).fail_execution(UUID(execution_id))


@activity.defn(name="complete_evidence_summary_work_set")
async def complete_evidence_summary_work_set(execution_id: str) -> str | None:
    """Refresh aggregate summary progress after one durable internal job finishes."""

    settings = get_settings()
    if not settings.database_url:
        raise RuntimeError("The durable worker requires DATABASE_URL.")
    work_set = await EvidenceSummaryStore(settings.database_url).refresh_work_set_for_execution(
        UUID(execution_id)
    )
    return work_set.status if work_set is not None else None


@activity.defn(name="preflight_source_candidates")
async def preflight_source_candidates(request_json: str) -> str:
    """Preflight only the server-selected, stored sources in one discovery batch."""

    settings = get_settings()
    if not settings.database_url:
        raise RuntimeError("The durable worker requires DATABASE_URL.")
    request = CandidatePreflightRequest.model_validate_json(request_json)
    secrets = DeploymentSecrets(settings)
    research_store = ResearchStore(settings.database_url, secrets.redact)
    workspace_id = await research_store.workspace_id_for_run(request.run_id)
    if workspace_id is None:
        raise RuntimeError("Candidate preflight run is unavailable.")
    service = CandidatePreflightService(
        research_store,
        EvidenceTrustService(WebTrustStore(settings.database_url, secrets.redact)),
    )
    await service.preflight_run(workspace_id, request.run_id, request.source_urls)
    return "ready"


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
        workflows=[EvidenceSummaryWorkflow, CandidatePreflightWorkflow],
        activities=[
            execute_evidence_summary,
            fail_evidence_summary_execution,
            complete_evidence_summary_work_set,
            preflight_source_candidates,
            continue_unified_research,
        ],
    )
    await worker.run()


if __name__ == "__main__":
    asyncio.run(run_worker())
