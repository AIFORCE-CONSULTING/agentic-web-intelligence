"""Persisted candidate preflight before an operator selects evidence for use."""

from hashlib import sha256
from uuid import UUID

from temporalio.client import Client

from app.web_research.contracts import ToolPolicyError, ToolProviderError, ToolRetrievalError
from app.web_research.store import ResearchStore
from app.web_research.workflow import run_extract_workflow
from app.web_trust.contracts import CandidatePreflightRequest
from app.web_trust.service import EvidenceTrustService
from app.web_trust.workflow import CandidatePreflightWorkflow

DIRECT_PREFLIGHT_SOURCE_LIMIT = 2


class CandidatePreflightUnavailable(RuntimeError):
    """Raised when platform-owned candidate preflight cannot be scheduled."""


class CandidatePreflightService:
    """Retrieve each discovered candidate once and retain its local readiness result."""

    def __init__(self, research_store: ResearchStore, trust_service: EvidenceTrustService) -> None:
        self._research_store = research_store
        self._trust_service = trust_service

    async def preflight_run(
        self, workspace_id: UUID, run_id: UUID, source_urls: list[str] | None = None
    ) -> None:
        """Process pending candidates sequentially through the governed extraction boundary."""

        run = await self._research_store.get_run(workspace_id, run_id)
        if run is None:
            raise CandidatePreflightUnavailable(
                "The research run is unavailable for candidate preflight."
            )
        allowed_urls = set(source_urls) if source_urls is not None else None
        stored_evidence = {evidence.url: evidence for evidence in run.evidence}
        for source in run.sources:
            if allowed_urls is not None and source.url not in allowed_urls:
                continue
            if source.preflight_status not in {"pending", "checking"}:
                continue
            evidence = stored_evidence.get(source.url)
            if evidence is None:
                await self._research_store.mark_candidate_checking(run_id, source.url)
                try:
                    evidence = await run_extract_workflow(source.url)
                except ToolPolicyError as error:
                    await self._research_store.record_candidate_preflight(
                        run_id, source.url, "blocked", str(error)
                    )
                    continue
                except ToolRetrievalError as error:
                    await self._research_store.record_candidate_preflight(
                        run_id, source.url, "unreachable", str(error)
                    )
                    continue
                except ToolProviderError as error:
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
                trust_disposition=evaluation.disposition,
            )
        await self._research_store.complete_candidate_preflight(run_id)


class CandidatePreflightTemporalBoundary:
    """Schedule only the stored candidate-preflight workflow selected by platform policy."""

    def __init__(self, address: str | None, namespace: str, task_queue: str) -> None:
        self._address = address
        self._namespace = namespace
        self._task_queue = task_queue

    async def schedule(self, run_id: UUID, source_urls: list[str]) -> None:
        if not self._address:
            raise CandidatePreflightUnavailable("Durable execution is not configured.")
        request = CandidatePreflightRequest(run_id=run_id, source_urls=source_urls)
        payload = request.model_dump_json()
        batch_id = sha256(payload.encode("utf-8")).hexdigest()[:16]
        client = await Client.connect(self._address, namespace=self._namespace)
        await client.start_workflow(
            CandidatePreflightWorkflow.run,
            payload,
            id=f"candidate-preflight-{run_id}-{batch_id}",
            task_queue=self._task_queue,
        )
