"""Server-only orchestration service that turns bounded proposals into authority."""

from uuid import UUID, uuid4

from app.agent_runtime.contracts import (
    ApprovedPlanStep,
    PlanStepProposal,
    RuntimeHandoff,
    RuntimeRun,
    RuntimeStep,
)
from app.agent_runtime.policy import (
    ALLOWED_HANDOFFS,
    MAX_RESEARCH_STEPS,
    ROLE_CAPABILITIES,
    ROLE_TIMEOUT_SECONDS,
)
from app.agent_runtime.store import RuntimeHandoffError, RuntimeStore


class RuntimePlanError(ValueError):
    """Raised when a proposal cannot become an approved runtime plan."""


class RuntimeService:
    """Authority boundary used by trusted server orchestration code only.

    This class is intentionally not registered as an HTTP route or MCP tool.
    """

    def __init__(self, store: RuntimeStore) -> None:
        self._store = store

    async def start_run(self, goal: str) -> RuntimeRun:
        """Create a server-owned planner assignment and begin the planning phase."""

        run = await self._store.create_run(goal)
        transitioned = await self._store.transition_run(run.id, "planning")
        assert transitioned is not None
        return transitioned

    async def approve_plan(
        self, run_id: UUID, proposals: list[PlanStepProposal]
    ) -> RuntimeRun:
        """Materialize only policy-approved roles with fixed capabilities."""

        run = await self._require_run(run_id)
        if run.status != "planning":
            raise RuntimePlanError("A plan can be approved only while the run is planning.")
        assignments = self._approved_assignments(proposals)
        materialized = await self._store.materialize_plan(run_id, assignments)
        assert materialized is not None
        return materialized

    async def begin_execution(self, run_id: UUID) -> RuntimeRun:
        """Move an approved plan into execution through the finite state machine."""

        transitioned = await self._store.transition_run(run_id, "executing")
        if transitioned is None:
            raise RuntimePlanError("Runtime run was not found.")
        return transitioned

    async def activate_researcher(self, run_id: UUID) -> RuntimeStep:
        """Activate the only step that may request Phase 2 web capabilities."""

        run = await self._require_run(run_id)
        if run.status != "executing":
            raise RuntimePlanError("A researcher can run only while the runtime is executing.")
        researcher = next((step for step in run.steps if step.role == "researcher"), None)
        if researcher is None:
            raise RuntimePlanError("Runtime run has no approved researcher step.")
        await self._store.activate_step(run_id, researcher.id)
        return researcher.model_copy(update={"status": "active", "attempt_count": researcher.attempt_count + 1})

    async def authorize_capability(self, step: RuntimeStep, capability: str) -> None:
        """Reject an executor request unless the stored step grant permits it."""

        if capability not in step.allowed_capabilities:
            raise RuntimePlanError(
                f"The {step.role} step is not authorized to invoke {capability}."
            )

    async def complete_research(self, run_id: UUID, step_id: UUID) -> RuntimeRun:
        """Close the researcher step and move the run to the reviewer gate."""

        await self._store.complete_step(run_id, step_id)
        transitioned = await self._store.transition_run(run_id, "reviewing")
        assert transitioned is not None
        return transitioned

    async def fail_research(self, run_id: UUID, step_id: UUID, reason: str) -> RuntimeRun:
        """Record a failed deterministic execution without attempting an implicit retry."""

        await self._store.fail_step(run_id, step_id, reason)
        transitioned = await self._store.transition_run(run_id, "failed")
        assert transitioned is not None
        return transitioned

    async def record_tool_outcome(
        self, run_id: UUID, step_id: UUID, tool_name: str, details: dict[str, object]
    ) -> None:
        """Record bounded, non-secret tool outcome metadata in the runtime audit stream."""

        await self._store.record_event(
            run_id,
            "runtime.tool.succeeded",
            {"step_id": str(step_id), "tool_name": tool_name, **details},
        )

    async def remember_research_query(self, run_id: UUID, step_id: UUID, query: str) -> None:
        """Retain a bounded query reference for this run only."""

        await self._store.record_memory(
            run_id, "research_query", {"query": query}, source_step_id=step_id
        )

    async def remember_source_reference(
        self, run_id: UUID, step_id: UUID, url: str, content_hash: str
    ) -> None:
        """Retain provenance references, never the raw retrieved page body."""

        await self._store.record_memory(
            run_id,
            "source_reference",
            {"url": url, "content_hash": content_hash},
            source_step_id=step_id,
        )

    async def handoff(
        self, run_id: UUID, sender_step_id: UUID, recipient_step_id: UUID, content: str
    ) -> RuntimeHandoff:
        """Create an auditable handoff only along a policy-defined role edge."""

        run = await self._require_run(run_id)
        steps = {step.id: step for step in run.steps}
        sender = steps.get(sender_step_id)
        recipient = steps.get(recipient_step_id)
        if sender is None or recipient is None:
            raise RuntimeHandoffError("Handoff steps must belong to the same runtime run.")
        if recipient.role not in ALLOWED_HANDOFFS[sender.role]:
            raise RuntimeHandoffError(
                f"A {sender.role} step cannot hand off work to a {recipient.role} step."
            )
        return await self._store.create_handoff(run_id, sender_step_id, recipient_step_id, content)

    async def _require_run(self, run_id: UUID) -> RuntimeRun:
        run = await self._store.get_run(run_id)
        if run is None:
            raise RuntimePlanError("Runtime run was not found.")
        return run

    @staticmethod
    def _approved_assignments(proposals: list[PlanStepProposal]) -> list[ApprovedPlanStep]:
        researcher_count = sum(proposal.role == "researcher" for proposal in proposals)
        if not proposals or researcher_count == 0:
            raise RuntimePlanError("An approved plan requires at least one researcher step.")
        if researcher_count > MAX_RESEARCH_STEPS:
            raise RuntimePlanError(
                f"An approved plan permits at most {MAX_RESEARCH_STEPS} researcher steps."
            )
        if proposals[-1].role != "reviewer" or sum(
            proposal.role == "reviewer" for proposal in proposals
        ) != 1:
            raise RuntimePlanError("An approved plan requires exactly one final reviewer step.")
        if any(proposal.role == "reviewer" for proposal in proposals[:-1]):
            raise RuntimePlanError("Reviewer work may occur only after researcher steps.")

        assignments: list[ApprovedPlanStep] = []
        for proposal in proposals:
            step_id = uuid4()
            assignments.append(
                ApprovedPlanStep(
                    id=step_id,
                    role=proposal.role,
                    title=proposal.title,
                    allowed_capabilities=list(ROLE_CAPABILITIES[proposal.role]),
                    idempotency_key=f"{proposal.role}:{step_id}",
                    timeout_seconds=ROLE_TIMEOUT_SECONDS[proposal.role],
                )
            )
        return assignments
