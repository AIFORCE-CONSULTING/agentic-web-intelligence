"""Platform authority service that turns bounded proposals into stored decisions."""

from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid4

from pydantic import ValidationError

from app.agent_runtime.contracts import (
    AUTHORITY_POLICY_VERSION,
    ApprovedPlanStep,
    AuthorizationDecision,
    AuthorizationDecisionReason,
    CapabilityRequest,
    McpExecutionCorrelation,
    PlanStepProposal,
    ReviewDecision,
    RuntimeHandoff,
    RuntimeRun,
    RuntimeStep,
)
from app.agent_runtime.policy import (
    ACTION_RESEARCH_STAGES,
    ALLOWED_HANDOFFS,
    MAX_OPERATOR_REVISION_APPROVALS,
    MAX_RESEARCH_ATTEMPTS,
    MAX_RESEARCH_STEPS,
    ROLE_CAPABILITIES,
    ROLE_TIMEOUT_SECONDS,
    authorization_explanation,
)
from app.agent_runtime.store import RuntimeHandoffError, RuntimeStore
from app.web_research.contracts import ExtractRequest, ResearchRun, SearchRequest


class ResearchAuthorityReader(Protocol):
    """Read official research status without granting RuntimeService write access."""

    async def get_run(self, workspace_id: UUID, run_id: UUID) -> ResearchRun | None: ...


class RuntimePlanError(ValueError):
    """Raised when a proposal cannot become an approved runtime plan."""


class RuntimeService:
    """Authority boundary used by trusted server orchestration code only.

    This class is intentionally not registered as an HTTP route or MCP tool.
    """

    def __init__(
        self,
        store: RuntimeStore,
        research_reader: ResearchAuthorityReader | None = None,
    ) -> None:
        self._store = store
        self._research_reader = research_reader

    async def ensure_research_assignment(
        self, workspace_id: UUID, research_run_id: UUID, goal: str
    ) -> RuntimeRun:
        """Create or reuse the one server-owned assignment for a research task."""

        return await self._store.ensure_research_assignment(
            workspace_id, research_run_id, goal
        )

    async def authorize_request(
        self, request: CapabilityRequest
    ) -> AuthorizationDecision:
        """Reload canonical facts, enforce limits, and persist allow or deny."""

        if self._research_reader is None:
            raise RuntimePlanError("Research authority persistence is not configured.")
        runtime = await self._store.get_run(request.runtime_run_id)
        research = await self._research_reader.get_run(
            request.workspace_id, request.research_run_id
        )
        reason: AuthorizationDecisionReason = "allowed"
        step = None
        normalized_query = ""
        try:
            if request.action == "web.search":
                normalized_query = SearchRequest.model_validate(
                    request.arguments, extra="forbid"
                ).query
            else:
                extraction = ExtractRequest.model_validate(
                    request.arguments, extra="forbid"
                )
                if extraction.url != request.resource_id:
                    raise ValueError("Extraction resource mismatch")
        except ValidationError:
            reason = "malformed_context"
        except ValueError:
            reason = "resource_out_of_scope"
        if reason != "allowed":
            pass
        elif runtime is None or runtime.status != "executing":
            reason = "run_inactive"
        elif runtime.workspace_id != request.workspace_id:
            reason = "wrong_workspace"
        elif runtime.research_run_id != request.research_run_id:
            reason = "wrong_research_task"
        else:
            step = next(
                (item for item in runtime.steps if item.id == request.runtime_step_id),
                None,
            )
            if step is None or step.status != "active" or step.role != "researcher":
                reason = "step_inactive"
            elif request.action not in step.allowed_capabilities:
                reason = "capability_not_granted"
            elif research is None:
                reason = "wrong_research_task"
            elif (
                research.status != request.research_status
                or research.status_version != request.research_status_version
            ):
                reason = "stale_authorization"
            elif research.status not in ACTION_RESEARCH_STAGES[request.action]:
                reason = "invalid_stage"
            elif request.action == "web.extract" and not await self._store.source_is_discovered(
                request.research_run_id, request.resource_id
            ):
                reason = "source_not_discovered"
            elif request.action == "web.search" and not await self._store.reserve_query(
                request.research_run_id,
                request.topic_id,
                normalized_query,
                request.purpose,
            ):
                reason = "retry_limit_exhausted"
            elif request.action == "web.extract" and not await self._store.reserve_source_attempt(
                request.research_run_id,
                request.topic_id,
                request.resource_id,
            ):
                reason = "attempt_limit_exhausted"

        decision = AuthorizationDecision(
            id=uuid4(),
            workspace_id=request.workspace_id,
            runtime_run_id=request.runtime_run_id,
            runtime_step_id=request.runtime_step_id,
            research_run_id=request.research_run_id,
            action=request.action,
            resource_type=request.resource_type,
            resource_id=request.resource_id,
            decision="allow" if reason == "allowed" else "deny",
            reason_code=reason,
            explanation=authorization_explanation(reason),
            authority_policy_version=AUTHORITY_POLICY_VERSION,
            request_facts={
                "argument_names": sorted(request.arguments),
                "purpose": request.purpose,
            },
            request_id=request.request_id,
            research_status_version=(
                research.status_version if research else request.research_status_version
            ),
            created_at=datetime.now(UTC),
        )
        return await self._store.record_authorization_decision(decision)

    async def register_discovered_source(
        self,
        research_run_id: UUID,
        topic_id: str,
        source_url: str,
        source_limit: int,
    ) -> bool:
        """Place a source in extraction scope without exceeding the task limit."""

        return await self._store.record_discovered_source(
            research_run_id,
            topic_id,
            source_url,
            source_limit=source_limit,
        )

    async def discovered_source_topic(
        self, research_run_id: UUID, source_url: str
    ) -> str | None:
        """Load topic scope from the authority store rather than the caller."""

        return await self._store.discovered_source_topic(research_run_id, source_url)

    async def begin_gap_search_round(self, research_run_id: UUID) -> int | None:
        """Reserve one of the two stored missing-topic search rounds."""

        return await self._store.begin_gap_round(research_run_id)

    async def verify_execution(
        self, correlation: McpExecutionCorrelation
    ) -> AuthorizationDecision:
        """Recheck a stored allow decision immediately before provider execution."""

        decision = await self._store.authorization_decision(
            correlation.authorization_decision_id
        )
        expected = (
            correlation.workspace_id,
            correlation.research_run_id,
            correlation.runtime_run_id,
            correlation.runtime_step_id,
            correlation.request_id,
            correlation.tool_name,
            correlation.resource_type,
            correlation.resource_id,
        )
        actual = (
            decision.workspace_id,
            decision.research_run_id,
            decision.runtime_run_id,
            decision.runtime_step_id,
            decision.request_id,
            decision.action,
            decision.resource_type,
            decision.resource_id,
        ) if decision else None
        if decision is None or decision.decision != "allow" or actual != expected:
            raise RuntimePlanError("No matching stored allow decision exists.")
        if self._research_reader is None:
            raise RuntimePlanError("Research authority persistence is not configured.")
        runtime = await self._store.get_run(
            correlation.runtime_run_id, correlation.workspace_id
        )
        research = await self._research_reader.get_run(
            correlation.workspace_id, correlation.research_run_id
        )
        step = next(
            (
                item
                for item in runtime.steps
                if item.id == correlation.runtime_step_id
            ),
            None,
        ) if runtime else None
        if (
            runtime is None
            or runtime.status != "executing"
            or runtime.research_run_id != correlation.research_run_id
            or step is None
            or step.status != "active"
            or correlation.tool_name not in step.allowed_capabilities
            or research is None
            or research.status_version != decision.research_status_version
            or research.status not in ACTION_RESEARCH_STAGES[correlation.tool_name]
        ):
            stale = decision.model_copy(
                update={
                    "id": uuid4(),
                    "decision": "deny",
                    "reason_code": "stale_authorization",
                    "explanation": authorization_explanation("stale_authorization"),
                    "created_at": datetime.now(UTC),
                }
            )
            await self._store.record_authorization_decision(stale)
            raise RuntimePlanError(stale.explanation)
        return decision

    async def start_run(self, goal: str, workspace_id: UUID) -> RuntimeRun:
        """Create a server-owned planner assignment and begin the planning phase."""

        run = await self._store.create_run(goal, workspace_id)
        transitioned = await self._store.transition_run(run.id, "planning")
        assert transitioned is not None
        return transitioned

    async def approve_plan(self, run_id: UUID, proposals: list[PlanStepProposal]) -> RuntimeRun:
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

        run = await self._require_run(run_id)
        if run.status == "executing":
            return run
        if run.status != "awaiting_approval":
            raise RuntimePlanError(
                "Execution can begin only after approval or a reviewer revision."
            )
        if not any(event.event_type == "runtime.approval.approved" for event in run.events):
            raise RuntimePlanError("Execution can begin only after recorded human approval.")
        transitioned = await self._store.transition_run(run_id, "executing")
        if transitioned is None:
            raise RuntimePlanError("Runtime run was not found.")
        return transitioned

    async def cancel_run(self, run_id: UUID) -> RuntimeRun:
        """Record a terminal cancellation before durable workers can start more work."""

        run = await self._require_run(run_id)
        if run.status in {"completed", "rejected", "failed", "cancelled"}:
            raise RuntimePlanError("Only a nonterminal runtime run may be cancelled.")
        transitioned = await self._store.transition_run(run_id, "cancelled")
        assert transitioned is not None
        return transitioned

    async def record_durable_execution_scheduled(self, run_id: UUID) -> RuntimeRun:
        """Persist a checkpoint after trusted code selects durable execution."""

        run = await self._require_human_approved_run(run_id)
        if any(event.event_type == "runtime.durable_execution.scheduled" for event in run.events):
            raise RuntimePlanError("Durable execution is already scheduled for this run.")
        await self._store.record_event(run_id, "runtime.durable_execution.scheduled", {})
        return await self._require_run(run_id)

    async def escalate_durable_ambiguity(self, run_id: UUID) -> RuntimeRun:
        """Stop uncertain durable work without retrying or preserving raw failure detail."""

        run = await self._require_run(run_id)
        if run.status == "cancelled":
            return run
        if run.status in {"completed", "rejected", "failed", "needs_attention"}:
            return run
        await self._store.record_event(
            run_id,
            "runtime.durable_execution.needs_attention",
            {"reason": "ambiguous_activity_outcome"},
        )
        escalated = await self._store.transition_run(run_id, "needs_attention")
        assert escalated is not None
        return escalated

    async def record_human_approval(self, run_id: UUID) -> RuntimeRun:
        """Persist a human approval independently of any scheduler."""

        run = await self._require_approval_gated_run(run_id)
        if any(event.event_type == "runtime.approval.approved" for event in run.events):
            raise RuntimePlanError("Human approval is already recorded for this runtime run.")
        await self._store.record_event(run_id, "runtime.approval.approved", {})
        return await self._require_run(run_id)

    async def reject_human_approval(self, run_id: UUID) -> RuntimeRun:
        """Persist a terminal rejection without coupling it to a scheduler."""

        await self._require_approval_gated_run(run_id)
        rejected = await self._store.transition_run(run_id, "rejected")
        assert rejected is not None
        return rejected

    async def activate_researcher(self, run_id: UUID) -> RuntimeStep:
        """Activate the only step that may request Phase 2 web capabilities."""

        run = await self._require_run(run_id)
        if run.status != "executing":
            raise RuntimePlanError("A researcher can run only while the runtime is executing.")
        researcher = next(
            (step for step in run.steps if step.role == "researcher" and step.status == "pending"),
            None,
        )
        if researcher is None:
            raise RuntimePlanError("Runtime run has no pending approved researcher step.")
        await self._store.activate_step(run_id, researcher.id, "executing")
        return researcher.model_copy(
            update={"status": "active", "attempt_count": researcher.attempt_count + 1}
        )

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

    async def activate_reviewer(self, run_id: UUID) -> RuntimeStep:
        """Activate the reviewer only at the review gate and with no tool grants."""

        run = await self._require_run(run_id)
        if run.status != "reviewing":
            raise RuntimePlanError("A reviewer can run only while the runtime is reviewing.")
        reviewer = next(
            (step for step in run.steps if step.role == "reviewer" and step.status == "pending"),
            None,
        )
        if reviewer is None:
            raise RuntimePlanError("Runtime run has no pending approved reviewer step.")
        await self._store.activate_step(run_id, reviewer.id, "reviewing")
        return reviewer.model_copy(
            update={"status": "active", "attempt_count": reviewer.attempt_count + 1}
        )

    async def accept_review(self, run_id: UUID, reviewer_step_id: UUID) -> RuntimeRun:
        """Complete a reviewer step and close a successfully reviewed run."""

        await self._store.complete_step(run_id, reviewer_step_id)
        transitioned = await self._store.transition_run(run_id, "completed")
        assert transitioned is not None
        return transitioned

    async def request_research_revision(
        self, run_id: UUID, reviewer_step_id: UUID, researcher_step_id: UUID, feedback: str
    ) -> RuntimeRun:
        """Create the one policy-bounded reviewer-to-researcher feedback handoff."""

        run = await self._require_run(run_id)
        researcher = next((step for step in run.steps if step.id == researcher_step_id), None)
        if researcher is None or researcher.role != "researcher":
            raise RuntimePlanError("Reviewer feedback must target this run's researcher step.")
        if researcher.attempt_count >= MAX_RESEARCH_ATTEMPTS:
            raise RuntimePlanError("The approved researcher retry budget is exhausted.")
        revised = await self._store.request_revision(
            run_id, reviewer_step_id, researcher_step_id, feedback
        )
        assert revised is not None
        return revised

    async def escalate_review(
        self, run_id: UUID, reviewer_step_id: UUID, reason: str
    ) -> RuntimeRun:
        """Close an unresolved review without an implicit or unbounded retry."""

        await self._store.record_event(
            run_id,
            "runtime.review.needs_attention",
            {"reviewer_step_id": str(reviewer_step_id), "reason": reason[:512]},
        )
        await self._store.complete_step(run_id, reviewer_step_id)
        transitioned = await self._store.transition_run(run_id, "needs_attention")
        assert transitioned is not None
        return transitioned

    async def approve_exception_revision(self, run_id: UUID) -> RuntimeRun:
        """Allow an operator-approved, bounded revision after review exhaustion only."""

        run = await self._require_run(run_id)
        if run.status != "needs_attention":
            raise RuntimePlanError("Only a run awaiting operator attention may be revised.")
        if not any(event.event_type == "runtime.review.needs_attention" for event in run.events):
            raise RuntimePlanError("This attention state is not eligible for a review revision.")
        if any(
            event.event_type == "runtime.durable_execution.needs_attention" for event in run.events
        ):
            raise RuntimePlanError("An ambiguous durable outcome cannot be retried as a revision.")
        approvals = sum(
            event.event_type == "runtime.review.exception_revision.approved" for event in run.events
        )
        if approvals >= MAX_OPERATOR_REVISION_APPROVALS:
            raise RuntimePlanError(
                "The operator revision budget is exhausted; close the run instead."
            )
        researcher = next((step for step in run.steps if step.role == "researcher"), None)
        reviewer = next((step for step in run.steps if step.role == "reviewer"), None)
        if researcher is None or reviewer is None:
            raise RuntimePlanError("Runtime run has no approved researcher/reviewer pair.")
        revised = await self._store.authorize_exception_revision(run_id, researcher.id, reviewer.id)
        assert revised is not None
        return revised

    async def close_attention_run(self, run_id: UUID) -> RuntimeRun:
        """Close an unresolved operator-attention wait without restarting any work."""

        run = await self._require_run(run_id)
        if run.status != "needs_attention":
            raise RuntimePlanError("Only a run awaiting operator attention may be closed.")
        await self._store.record_event(run_id, "runtime.attention.closed", {})
        closed = await self._store.transition_run(run_id, "cancelled")
        assert closed is not None
        return closed

    async def get_run(self, run_id: UUID) -> RuntimeRun:
        """Read one persisted run for an internal workflow node."""

        return await self._require_run(run_id)

    async def record_review_decision(
        self, run_id: UUID, reviewer_step_id: UUID, decision: ReviewDecision
    ) -> None:
        """Persist the typed outcome before it can affect run routing."""

        await self._store.record_event(
            run_id,
            "runtime.review.decided",
            {
                "reviewer_step_id": str(reviewer_step_id),
                "outcome": decision.outcome,
                "reason": decision.reason,
            },
        )

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

    async def _require_approval_gated_run(self, run_id: UUID) -> RuntimeRun:
        run = await self._require_run(run_id)
        if run.status != "awaiting_approval":
            raise RuntimePlanError("Only an approval-gated runtime run may be scheduled.")
        return run

    async def _require_human_approved_run(self, run_id: UUID) -> RuntimeRun:
        run = await self._require_approval_gated_run(run_id)
        if not any(event.event_type == "runtime.approval.approved" for event in run.events):
            raise RuntimePlanError("The runtime run has not received recorded human approval.")
        return run

    async def require_durable_execution_scheduled(self, run_id: UUID) -> RuntimeRun:
        """Confirm an operator may address an existing durable workflow."""

        run = await self._require_run(run_id)
        if not any(
            event.event_type == "runtime.durable_execution.scheduled" for event in run.events
        ):
            raise RuntimePlanError("Durable execution has not been scheduled for this run.")
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
        if (
            proposals[-1].role != "reviewer"
            or sum(proposal.role == "reviewer" for proposal in proposals) != 1
        ):
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
