"""Read-only durable-work view composed from existing application records."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.evidence_summaries.store import EvidenceSummaryStore
from app.web_research.contracts import ResearchRun
from app.web_research.store import ResearchStore
from app.web_trust.preflight import DIRECT_PREFLIGHT_SOURCE_LIMIT


class ResearchDurableOperation(BaseModel):
    """One direct or Temporal-backed operation owned by an existing store."""

    id: str
    operation_type: Literal["candidate_preflight", "evidence_summary"]
    route: Literal["direct", "temporal"]
    status: str
    updated_at: datetime
    failure_code: str | None = None
    failure_explanation: str | None = None


class ResearchDurableWork(BaseModel):
    """Workspace-safe durable work for one canonical research record."""

    research_run_id: UUID
    question: str
    research_status: str
    updated_at: datetime
    operations: list[ResearchDurableOperation] = Field(default_factory=list)


class ResearchDurableWorkList(BaseModel):
    items: list[ResearchDurableWork]


class ResearchDurableWorkService:
    """Compose operational visibility without creating another source of truth."""

    def __init__(
        self,
        research_store: ResearchStore,
        summary_store: EvidenceSummaryStore,
    ) -> None:
        self._research_store = research_store
        self._summary_store = summary_store

    async def list_for_workspace(
        self, workspace_id: UUID, limit: int
    ) -> list[ResearchDurableWork]:
        summaries = await self._research_store.list_runs(workspace_id, limit)
        items: list[ResearchDurableWork] = []
        for summary in summaries:
            item = await self.get(workspace_id, summary.id)
            if item is not None and item.operations:
                items.append(item)
        return items

    async def get(
        self, workspace_id: UUID, run_id: UUID
    ) -> ResearchDurableWork | None:
        run = await self._research_store.get_run(workspace_id, run_id)
        if run is None:
            return None
        operations = self._preflight_operations(run)
        summary = await self._summary_store.get_latest_execution_for_run(
            workspace_id, run_id
        )
        if summary is not None and summary.route != "undetermined":
            operations.append(
                ResearchDurableOperation(
                    id=str(summary.id),
                    operation_type="evidence_summary",
                    route="temporal" if summary.route == "durable" else "direct",
                    status=summary.status,
                    updated_at=summary.updated_at,
                    failure_code=(
                        run.failure_code if run.failed_stage == "summarizing" else None
                    ),
                    failure_explanation=(
                        run.failure_explanation
                        if run.failed_stage == "summarizing"
                        else None
                    ),
                )
            )
        return ResearchDurableWork(
            research_run_id=run.id,
            question=run.question,
            research_status=run.status,
            updated_at=run.updated_at,
            operations=operations,
        )

    @staticmethod
    def _preflight_operations(run: ResearchRun) -> list[ResearchDurableOperation]:
        if not run.sources:
            return []
        pending = any(
            source.preflight_status in {"pending", "checking"} for source in run.sources
        )
        failed = run.status == "failed" and run.failed_stage == "acquiring"
        checked_at = [
            source.preflight_checked_at
            for source in run.sources
            if source.preflight_checked_at is not None
        ]
        route_events = [
            event
            for event in run.audit_events
            if event.event_type == "research.candidate.preflight.routed"
        ]
        selected_route = (
            route_events[-1].details.get("route") if route_events else None
        )
        route = (
            selected_route
            if selected_route in {"direct", "temporal"}
            else (
                "direct"
                if len(run.sources) <= DIRECT_PREFLIGHT_SOURCE_LIMIT
                else "temporal"
            )
        )
        return [
            ResearchDurableOperation(
                id=f"candidate-preflight:{run.id}",
                operation_type="candidate_preflight",
                route=route,
                status="failed" if failed else "pending" if pending else "completed",
                updated_at=max(checked_at, default=run.updated_at),
                failure_code=run.failure_code if failed else None,
                failure_explanation=run.failure_explanation if failed else None,
            )
        ]
