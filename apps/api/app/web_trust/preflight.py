"""Persisted candidate preflight before an operator selects evidence for use."""

from collections.abc import Awaitable, Callable, Mapping
from hashlib import sha256
from typing import Any, Protocol, cast
from uuid import UUID, uuid4

from temporalio.client import Client

from app.agent_runtime.contracts import CapabilityRequest, McpExecutionCorrelation, RuntimeRun
from app.durable_execution.contracts import (
    CandidatePreflightWorkflowInput,
    WorkflowContinuationContext,
    WorkflowContinuationEnvelope,
)
from app.web_research.contracts import (
    Evidence,
    ToolPolicyError,
    ToolProviderError,
    ToolRetrievalError,
)
from app.web_research.store import ResearchStore
from app.web_research.workflow import run_extract_workflow
from app.web_trust.contracts import CandidatePreflightRequest
from app.web_trust.service import EvidenceTrustService
from app.web_trust.workflow import CandidatePreflightWorkflow

DIRECT_PREFLIGHT_SOURCE_LIMIT = 2


class CandidatePreflightUnavailable(RuntimeError):
    """Raised when platform-owned candidate preflight cannot be scheduled."""


class PreflightAuthority(Protocol):
    async def ensure_research_assignment(
        self, workspace_id: UUID, research_run_id: UUID, goal: str
    ) -> RuntimeRun: ...

    async def discovered_source_topic(
        self, research_run_id: UUID, source_url: str
    ) -> str | None: ...

    async def authorize_request(self, request: CapabilityRequest) -> Any: ...


class PreflightMcpInvoker(Protocol):
    async def invoke_authorized(
        self,
        correlation: McpExecutionCorrelation,
        arguments: Mapping[str, Any],
        authority: Any,
    ) -> object: ...


class CandidatePreflightService:
    """Retrieve each discovered candidate once and retain its local readiness result."""

    def __init__(self, research_store: ResearchStore, trust_service: EvidenceTrustService) -> None:
        self._research_store = research_store
        self._trust_service = trust_service

    async def preflight_run(
        self, workspace_id: UUID, run_id: UUID, source_urls: list[str] | None = None
    ) -> None:
        """Process candidates for the legacy caller pending unified-graph migration."""

        await self._preflight_run(
            workspace_id, run_id, source_urls, run_extract_workflow, False
        )

    async def preflight_run_authorized(
        self,
        workspace_id: UUID,
        run_id: UUID,
        authority: PreflightAuthority,
        mcp: PreflightMcpInvoker,
        source_urls: list[str] | None = None,
    ) -> None:
        """Extract candidates only through a stored RuntimeService allow decision."""

        async def extract(url: str) -> Evidence:
            run = await self._research_store.get_run(workspace_id, run_id)
            if run is None:
                raise CandidatePreflightUnavailable(
                    "The research run is unavailable for candidate preflight."
                )
            assignment = await authority.ensure_research_assignment(
                workspace_id, run_id, run.question
            )
            step = next(
                (
                    item
                    for item in assignment.steps
                    if item.role == "researcher" and item.status == "active"
                ),
                None,
            )
            topic_id = await authority.discovered_source_topic(run_id, url)
            if step is None or topic_id is None:
                raise ToolPolicyError(
                    "The source has no active, stored research authorization scope."
                )
            request_id = uuid4()
            arguments: dict[str, object] = {"url": url}
            request = CapabilityRequest(
                workspace_id=workspace_id,
                runtime_run_id=assignment.id,
                runtime_step_id=step.id,
                research_run_id=run_id,
                research_status=run.status,
                research_status_version=run.status_version,
                topic_id=topic_id,
                action="web.extract",
                resource_type="source",
                resource_id=url,
                arguments=arguments,
                request_id=request_id,
                purpose="candidate preflight",
            )
            decision = await authority.authorize_request(request)
            if decision.decision != "allow":
                raise ToolPolicyError(decision.explanation)
            result = await mcp.invoke_authorized(
                McpExecutionCorrelation(
                    workspace_id=workspace_id,
                    research_run_id=run_id,
                    runtime_run_id=assignment.id,
                    runtime_step_id=step.id,
                    authorization_decision_id=decision.id,
                    request_id=request_id,
                    tool_name="web.extract",
                    resource_type="source",
                    resource_id=url,
                ),
                arguments,
                authority,
            )
            return cast(Evidence, result)

        await self._preflight_run(workspace_id, run_id, source_urls, extract, True)

    async def _preflight_run(
        self,
        workspace_id: UUID,
        run_id: UUID,
        source_urls: list[str] | None,
        extract: Callable[[str], Awaitable[Evidence]],
        provider_failure_is_system: bool,
    ) -> None:
        """Share evidence persistence and trust evaluation across caller migration."""

        run = await self._research_store.get_run(workspace_id, run_id)
        if run is None:
            raise CandidatePreflightUnavailable(
                "The research run is unavailable for candidate preflight."
            )
        allowed_urls = set(source_urls) if source_urls is not None else None
        stored_evidence = {
            evidence.requested_url or evidence.url: evidence for evidence in run.evidence
        }
        for source in run.sources:
            if allowed_urls is not None and source.url not in allowed_urls:
                continue
            if source.preflight_status not in {"pending", "checking"}:
                continue
            evidence = stored_evidence.get(source.url)
            if evidence is None:
                await self._research_store.mark_candidate_checking(run_id, source.url)
                try:
                    evidence = await extract(source.url)
                except ToolPolicyError as error:
                    await self._research_store.record_candidate_preflight(
                        run_id,
                        source.url,
                        "blocked",
                        str(error),
                        redirect_result=error.redirect_result,
                    )
                    continue
                except ToolRetrievalError as error:
                    await self._research_store.record_candidate_preflight(
                        run_id, source.url, "unreachable", str(error)
                    )
                    continue
                except ToolProviderError as error:
                    if provider_failure_is_system:
                        await self._research_store.transition_status(
                            run_id,
                            run.status,
                            run.status_version,
                            "failed",
                            uuid4(),
                            "The governed extraction provider is unavailable.",
                            failed_stage=run.status,
                            failure_code="extraction_unavailable",
                            failure_explanation=(
                                "The evidence extraction provider is temporarily unavailable."
                            ),
                            retryable=True,
                        )
                        raise CandidatePreflightUnavailable(
                            "The evidence extraction provider is temporarily unavailable."
                        ) from error
                    await self._research_store.record_candidate_preflight(
                        run_id, source.url, "unreachable", str(error)
                    )
                    continue
                await self._research_store.save_evidence(run_id, evidence)
            evaluation = await self._trust_service.evaluate(workspace_id, run_id, evidence)
            status = (
                "ready_to_extract"
                if evaluation.disposition in {"eligible", "eligible_with_notice"}
                else evaluation.disposition
            )
            await self._research_store.record_candidate_preflight(
                run_id,
                source.url,
                status,
                content_type=evidence.content_type,
                content_hash=evidence.content_hash,
                final_url=evidence.url,
                redirect_result=evidence.redirect_result,
                trust_disposition=evaluation.disposition,
            )
        await self._research_store.complete_candidate_preflight(run_id)


class CandidatePreflightTemporalBoundary:
    """Schedule only the stored candidate-preflight workflow selected by platform policy."""

    def __init__(self, address: str | None, namespace: str, task_queue: str) -> None:
        self._address = address
        self._namespace = namespace
        self._task_queue = task_queue

    async def schedule(
        self,
        run_id: UUID,
        source_urls: list[str],
        continuation: WorkflowContinuationContext,
    ) -> None:
        if not self._address:
            raise CandidatePreflightUnavailable("Durable execution is not configured.")
        request = CandidatePreflightRequest(run_id=run_id, source_urls=source_urls)
        payload = request.model_dump_json()
        batch_id = sha256(payload.encode("utf-8")).hexdigest()[:16]
        wait = continuation.wait(batch_id, "candidate_preflight")
        client = await Client.connect(self._address, namespace=self._namespace)
        await client.start_workflow(
            CandidatePreflightWorkflow.run,
            CandidatePreflightWorkflowInput(
                request_json=payload,
                continuation=WorkflowContinuationEnvelope(
                    wait=wait,
                    result_record_id=batch_id,
                    outcome="completed",
                ),
            ),
            id=f"candidate-preflight-{run_id}-{batch_id}",
            task_queue=self._task_queue,
        )
