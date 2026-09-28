"""Canonical LangGraph structure and checkpoint lifecycle for research."""

import argparse
import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from typing import Any, Literal, Protocol, TypedDict, cast
from uuid import NAMESPACE_URL, UUID, uuid5

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from app.agentic_research.contracts import ResearchTopic, TopicSourceAssociation
from app.agentic_research.relevance import TopicRelevanceUnavailable
from app.agentic_research.reporting import ResearchReportingUnavailable
from app.agentic_research.store import AgenticResearchStoreUnavailable
from app.agentic_research.topic_planning import (
    TopicPlanningService,
    TopicPlanningUnavailable,
)
from app.durable_execution.contracts import (
    UNIFIED_RESEARCH_WORKFLOW_VERSION,
    WorkflowContinuationEnvelope,
)
from app.evidence_summaries.service import EvidenceSummaryUnavailable
from app.evidence_summaries.store import EvidenceSummaryStoreUnavailable
from app.settings import get_settings
from app.web_research.contracts import ResearchRun, ToolProviderError
from app.web_research.store import ResearchStore
from app.web_trust.preflight import CandidatePreflightUnavailable
from app.web_trust.store import WebTrustStoreUnavailable

MAX_GAP_SEARCH_ROUNDS = 2
CHECKPOINT_STARTUP_CLEANUP_LIMIT = 100
WORKFLOW_DEPENDENCY_ERRORS = (
    AgenticResearchStoreUnavailable,
    CandidatePreflightUnavailable,
    EvidenceSummaryStoreUnavailable,
    EvidenceSummaryUnavailable,
    ResearchReportingUnavailable,
    ToolProviderError,
    TopicPlanningUnavailable,
    TopicRelevanceUnavailable,
    WebTrustStoreUnavailable,
)


class ResearchWorkflowUnavailable(RuntimeError):
    """Raised when required workflow infrastructure cannot start or resume research."""


class ResearchWorkflowConflict(RuntimeError):
    """Raised when official research state changed during one graph node."""


class ResearchWorkflowEntry(Protocol):
    """Thin application boundary used by the existing Discover Sources route."""

    async def start_or_resume(
        self,
        workspace_id: UUID,
        question: str,
        source_limit: int,
    ) -> tuple[ResearchRun, bool]: ...

    async def resume_after_review(
        self,
        workspace_id: UUID,
        research_run_id: UUID,
        source_url: str,
        content_hash: str,
    ) -> ResearchRun: ...


class CompiledResearchGraph(Protocol):
    """Minimal async interface supplied by a compiled LangGraph."""

    async def ainvoke(
        self, state: Any, config: dict[str, Any]
    ) -> dict[str, Any]: ...


class ResearchAssignmentService(Protocol):
    async def ensure_research_assignment(
        self, workspace_id: UUID, research_run_id: UUID, goal: str
    ) -> Any: ...


class WorkflowContinuationStore(Protocol):
    async def get_run(self, workspace_id: UUID, run_id: UUID) -> ResearchRun | None: ...

    async def claim_workflow_continuation(
        self,
        idempotency_key: str,
        research_run_id: UUID,
        execution_id: str,
        wait_type: str,
        outcome: str,
    ) -> bool: ...

    async def finish_workflow_continuation(
        self, idempotency_key: str, status: str, explanation: str | None = None
    ) -> None: ...


class DurableResultVerifier(Protocol):
    async def verify_result(self, envelope: WorkflowContinuationEnvelope) -> bool: ...


class ResearchWorkflowContinuation:
    """Validate one Temporal result and resume the same stored graph thread once."""

    def __init__(
        self,
        store: WorkflowContinuationStore,
        graph: CompiledResearchGraph,
        checkpoints: "ResearchCheckpointLifecycle",
        result_verifier: DurableResultVerifier,
    ) -> None:
        self._store = store
        self._graph = graph
        self._checkpoints = checkpoints
        self._result_verifier = result_verifier

    async def continue_after(self, envelope: WorkflowContinuationEnvelope) -> str:
        wait = envelope.wait
        try:
            run_id = UUID(wait.thread.research_run_id)
            workspace_id = UUID(wait.thread.workspace_id)
        except ValueError as error:
            raise ResearchWorkflowUnavailable(
                "The durable continuation identity is invalid."
            ) from error
        if (
            wait.thread.thread_id != str(run_id)
            or wait.thread.checkpoint_namespace != UNIFIED_RESEARCH_WORKFLOW_VERSION
        ):
            raise ResearchWorkflowUnavailable(
                "The durable continuation does not match the research graph."
            )
        run = await self._store.get_run(workspace_id, run_id)
        if run is None:
            raise ResearchWorkflowUnavailable(
                "The durable continuation research record is unavailable."
            )
        claimed = await self._store.claim_workflow_continuation(
            wait.idempotency_key,
            run_id,
            wait.execution_id,
            wait.wait_type,
            envelope.outcome,
        )
        if not claimed:
            return "duplicate"
        if (
            run.status != wait.expected_research_status
            or run.status_version != wait.expected_status_version
        ):
            await self._store.finish_workflow_continuation(
                wait.idempotency_key,
                "stale",
                "Official research status no longer matches the durable wait.",
            )
            return "stale"
        if not await self._result_verifier.verify_result(envelope):
            await self._store.finish_workflow_continuation(
                wait.idempotency_key,
                "failed",
                "The durable result record was not ready for continuation.",
            )
            raise ResearchWorkflowUnavailable(
                "The durable result record is not ready for continuation."
            )
        await self._graph.ainvoke(
            Command(resume={"outcome": envelope.outcome}),
            self._checkpoints.graph_config(run_id),
        )
        await self._store.finish_workflow_continuation(
            wait.idempotency_key, "completed"
        )
        return "completed"


class UnifiedResearchWorkflowEntry:
    """Start or resume the one checkpointed graph for a canonical research task."""

    def __init__(
        self,
        store: ResearchStore,
        runtime_service: ResearchAssignmentService,
        checkpoints: "ResearchCheckpointLifecycle",
        graph: CompiledResearchGraph,
        temporal_ready: Callable[[], Awaitable[bool]],
    ) -> None:
        self._store = store
        self._runtime_service = runtime_service
        self._checkpoints = checkpoints
        self._graph = graph
        self._temporal_ready = temporal_ready

    async def start_or_resume(
        self,
        workspace_id: UUID,
        question: str,
        source_limit: int,
    ) -> tuple[ResearchRun, bool]:
        checkpoint_status = await self._checkpoints.readiness()
        if not checkpoint_status.ready:
            raise ResearchWorkflowUnavailable(checkpoint_status.detail)
        if not await self._temporal_ready():
            raise ResearchWorkflowUnavailable("Durable execution is unavailable.")
        run, created = await self._store.get_or_create_run(workspace_id, question)
        await self._runtime_service.ensure_research_assignment(
            workspace_id, run.id, question
        )
        if run.status == "failed":
            if run.failed_stage is None:
                raise ResearchWorkflowUnavailable(
                    "The failed research record has no safe resume stage."
                )
            transition_id = uuid5(
                NAMESPACE_URL,
                (
                    f"{UNIFIED_RESEARCH_WORKFLOW_VERSION}:{run.id}:retry:"
                    f"{run.status_version}:{run.failed_stage}"
                ),
            )
            resumed = await self._store.transition_status(
                run.id,
                run.status,
                run.status_version,
                run.failed_stage,
                transition_id,
                "Operator retried the failed research workflow.",
            )
            run = await self._store.get_run(workspace_id, run.id)
            if run is None:
                raise ResearchWorkflowUnavailable(
                    "The research record could not be reloaded for retry."
                )
            if not resumed and run.status == "failed":
                raise ResearchWorkflowConflict(
                    "Official research status changed while retrying the workflow."
                )
        if run.status != "completed":
            await self._graph.ainvoke(
                {
                    "workspace_id": workspace_id,
                    "run_id": run.id,
                    "question": question,
                    "source_limit": source_limit,
                    "stage": run.status,
                    "canonical_status": run.status,
                    "status_version": run.status_version,
                },
                self._checkpoints.graph_config(run.id),
            )
        persisted = await self._store.get_run(workspace_id, run.id)
        if persisted is None:
            raise ResearchWorkflowUnavailable(
                "The research record could not be reloaded after workflow execution."
            )
        return persisted, created

    async def resume_after_review(
        self,
        workspace_id: UUID,
        research_run_id: UUID,
        source_url: str,
        content_hash: str,
    ) -> ResearchRun:
        """Resume the stored review interrupt after an exact acceptance exists."""

        checkpoint_status = await self._checkpoints.readiness()
        if not checkpoint_status.ready:
            raise ResearchWorkflowUnavailable(checkpoint_status.detail)
        run = await self._store.get_run(workspace_id, research_run_id)
        if run is None:
            raise ResearchWorkflowUnavailable("The research record is unavailable.")
        if run.status != "awaiting_review":
            raise ResearchWorkflowConflict(
                "The research workflow is not waiting for human review."
            )
        await self._graph.ainvoke(
            Command(
                resume={
                    "outcome": "accepted",
                    "source_url": source_url,
                    "content_hash": content_hash,
                }
            ),
            self._checkpoints.graph_config(research_run_id),
        )
        persisted = await self._store.get_run(workspace_id, research_run_id)
        if persisted is None:
            raise ResearchWorkflowUnavailable(
                "The research record could not be reloaded after human review."
            )
        return persisted


class CheckpointCleanupStore(Protocol):
    """Business-store operations needed by checkpoint maintenance."""

    async def checkpoint_cleanup_candidates(self, limit: int = 100) -> list[UUID]: ...

    async def checkpoint_cleanup_backlog(self) -> int: ...

    async def record_checkpoint_cleanup(
        self, run_id: UUID, outcome: str, explanation: str | None = None
    ) -> None: ...


class AsyncCheckpointSaver(Protocol):
    """Official saver operations used without depending on its table layout."""

    async def setup(self) -> None: ...

    async def adelete_thread(self, thread_id: str) -> None: ...

    def alist(
        self,
        config: dict[str, Any] | None,
        *,
        limit: int | None = None,
    ) -> AsyncIterator[Any]: ...


@dataclass(frozen=True)
class CheckpointReadiness:
    """Safe operational status for checkpoint infrastructure."""

    ready: bool
    backlog: int
    detail: str


class ResearchCheckpointLifecycle:
    """Own the official PostgreSQL checkpointer lifecycle for one API process."""

    def __init__(
        self,
        database_url: str | None,
        cleanup_store: CheckpointCleanupStore,
        *,
        startup_cleanup_limit: int = CHECKPOINT_STARTUP_CLEANUP_LIMIT,
        saver_context_factory: Callable[[], AbstractAsyncContextManager[Any]] | None = None,
    ) -> None:
        self._database_url = database_url
        self._cleanup_store = cleanup_store
        self._startup_cleanup_limit = startup_cleanup_limit
        self._saver_context_factory = saver_context_factory
        self._saver_context: AbstractAsyncContextManager[Any] | None = None
        self._saver: AsyncCheckpointSaver | None = None
        self._setup_error: str | None = None
        self._cleanup_backlog = 0

    @staticmethod
    def graph_config(research_run_id: UUID) -> dict[str, dict[str, str]]:
        """Return the one stable graph identity for a research task."""

        return {
            "configurable": {
                "thread_id": str(research_run_id),
                "checkpoint_ns": UNIFIED_RESEARCH_WORKFLOW_VERSION,
            }
        }

    async def start(self) -> AsyncCheckpointSaver:
        """Initialize the official saver and retry bounded terminal cleanup."""

        if not self._database_url and self._saver_context_factory is None:
            self._setup_error = "PostgreSQL is not configured for research checkpoints."
            raise RuntimeError(self._setup_error)
        if self._saver is not None:
            return self._saver

        context = (
            self._saver_context_factory()
            if self._saver_context_factory is not None
            else AsyncPostgresSaver.from_conn_string(
                cast(str, self._database_url),
                serde=JsonPlusSerializer(
                    pickle_fallback=False,
                    allowed_json_modules=(),
                    allowed_msgpack_modules=(),
                ),
            )
        )
        self._saver_context = context
        try:
            saver = cast(AsyncCheckpointSaver, await context.__aenter__())
            await saver.setup()
            self._saver = saver
            self._setup_error = None
            await self.retry_completed_cleanup(self._startup_cleanup_limit)
            return saver
        except Exception as error:
            self._setup_error = "Research checkpoint persistence is unavailable."
            self._saver = None
            if self._saver_context is not None:
                await self._saver_context.__aexit__(type(error), error, error.__traceback__)
                self._saver_context = None
            raise RuntimeError(self._setup_error) from error

    async def stop(self) -> None:
        """Release the saver connection context owned by this process."""

        context = self._saver_context
        self._saver = None
        self._saver_context = None
        if context is not None:
            await context.__aexit__(None, None, None)

    def saver(self) -> AsyncCheckpointSaver:
        """Return the initialized saver or fail without an in-memory fallback."""

        if self._saver is None:
            raise RuntimeError("Research checkpoint persistence is not ready.")
        return self._saver

    async def readiness(self) -> CheckpointReadiness:
        """Report setup failure or cleanup backlog without exposing connection data."""

        if self._saver is None:
            return CheckpointReadiness(
                ready=False,
                backlog=self._cleanup_backlog,
                detail=self._setup_error or "Research checkpoint persistence is not started.",
            )
        self._cleanup_backlog = await self._cleanup_store.checkpoint_cleanup_backlog()
        if self._cleanup_backlog:
            return CheckpointReadiness(
                ready=False,
                backlog=self._cleanup_backlog,
                detail="Completed research checkpoint cleanup is pending.",
            )
        return CheckpointReadiness(
            ready=True,
            backlog=0,
            detail="Research checkpoint persistence is ready.",
        )

    async def delete_thread(self, research_run_id: UUID) -> bool:
        """Delete framework bookmarks after business completion and audit the result."""

        try:
            await self.saver().adelete_thread(str(research_run_id))
        except Exception:
            await self._cleanup_store.record_checkpoint_cleanup(
                research_run_id,
                "failed",
                "Framework checkpoint deletion failed and will be retried.",
            )
            return False
        await self._cleanup_store.record_checkpoint_cleanup(
            research_run_id, "succeeded"
        )
        return True

    async def retry_completed_cleanup(self, limit: int | None = None) -> int:
        """Retry the oldest bounded batch of completed research threads."""

        batch_limit = limit or self._startup_cleanup_limit
        candidates = await self._cleanup_store.checkpoint_cleanup_candidates(batch_limit)
        for research_run_id in candidates:
            await self.delete_thread(research_run_id)
        self._cleanup_backlog = await self._cleanup_store.checkpoint_cleanup_backlog()
        return self._cleanup_backlog

    async def delete_obsolete_threads(self, limit: int = 100) -> int:
        """Delete a bounded batch of old local threads through the official API."""

        saver = self.saver()
        thread_ids: list[str] = []
        seen: set[str] = set()
        async for checkpoint in saver.alist(None, limit=limit):
            config = getattr(checkpoint, "config", None) or checkpoint[0]
            thread_id = config.get("configurable", {}).get("thread_id")
            if thread_id and thread_id not in seen:
                seen.add(thread_id)
                thread_ids.append(thread_id)
        for thread_id in thread_ids:
            await saver.adelete_thread(thread_id)
        await saver.setup()
        return len(thread_ids)

ResearchStage = Literal[
    "requested",
    "topics_planned",
    "sources_discovered",
    "evidence_acquired",
    "awaiting_preflight",
    "relevance_decided",
    "summaries_stored",
    "awaiting_summaries",
    "coverage_complete",
    "coverage_incomplete",
    "awaiting_review",
    "report_stored",
    "completed",
    "failed",
    "cancelled",
]


class ResearchWorkflowState(TypedDict, total=False):
    """Bounded working context; PostgreSQL remains the official record."""

    workspace_id: UUID
    run_id: UUID
    question: str
    source_limit: int
    stage: ResearchStage
    topics: list[ResearchTopic]
    new_source_urls: list[str]
    discovered_source_count: int
    source_topics: list[TopicSourceAssociation]
    relevant_sources: list[TopicSourceAssociation]
    review_required_sources: list[dict[str, str]]
    uncovered_topic_ids: list[str]
    gap_search_rounds: int
    failure_reason: str
    failure_code: str
    failure_explanation: str
    retryable: bool
    failed_stage: str
    canonical_status: str
    status_version: int


ResearchNode = Callable[[ResearchWorkflowState], Awaitable[ResearchWorkflowState]]


def topic_planning_node(service: TopicPlanningService) -> ResearchNode:
    """Adapt the existing planning service to one LangGraph stage."""

    async def plan_topics(state: ResearchWorkflowState) -> ResearchWorkflowState:
        plan = await service.plan(
            state["workspace_id"],
            state["run_id"],
            state["question"],
        )
        return {"topics": plan.root, "stage": "topics_planned"}

    return plan_topics


class ResearchWorkflowNodes:
    """Typed platform operations used by the canonical research graph."""

    def __init__(
        self,
        *,
        plan_topics: ResearchNode,
        search_topics: ResearchNode,
        acquire_evidence: ResearchNode,
        evaluate_relevance: ResearchNode,
        summarize_evidence: ResearchNode,
        assess_topic_coverage: ResearchNode,
        search_missing_topic: ResearchNode,
        generate_final_report: ResearchNode,
        complete_research: ResearchNode,
        fail_durable_work: ResearchNode,
    ) -> None:
        self.plan_topics = plan_topics
        self.search_topics = search_topics
        self.acquire_evidence = acquire_evidence
        self.evaluate_relevance = evaluate_relevance
        self.summarize_evidence = summarize_evidence
        self.assess_topic_coverage = assess_topic_coverage
        self.search_missing_topic = search_missing_topic
        self.generate_final_report = generate_final_report
        self.complete_research = complete_research
        self.fail_durable_work = fail_durable_work


class CanonicalResearchWorkflowNodes:
    """Make ResearchStore the sole business-status writer around service nodes."""

    def __init__(self, nodes: ResearchWorkflowNodes, store: ResearchStore) -> None:
        self._nodes = nodes
        self._store = store

    def wrapped(self) -> ResearchWorkflowNodes:
        return ResearchWorkflowNodes(
            plan_topics=self._transitioning(
                "plan_topics", "planning", self._nodes.plan_topics, lambda _: "discovering"
            ),
            search_topics=self._transitioning(
                "search_topics", "discovering", self._nodes.search_topics, lambda _: "acquiring"
            ),
            acquire_evidence=self._transitioning(
                "acquire_evidence",
                "acquiring",
                self._nodes.acquire_evidence,
                lambda update: (
                    None
                    if update.get("stage") == "awaiting_preflight"
                    else "evaluating_relevance"
                ),
            ),
            evaluate_relevance=self._transitioning(
                "evaluate_relevance",
                "evaluating_relevance",
                self._nodes.evaluate_relevance,
                lambda update: (
                    "awaiting_review"
                    if update.get("stage") == "awaiting_review"
                    else "summarizing"
                ),
            ),
            summarize_evidence=self._transitioning(
                "summarize_evidence",
                "summarizing",
                self._nodes.summarize_evidence,
                lambda update: (
                    None
                    if update.get("stage") == "awaiting_summaries"
                    else "assessing_coverage"
                ),
            ),
            assess_topic_coverage=self._transitioning(
                "assess_topic_coverage",
                "assessing_coverage",
                self._nodes.assess_topic_coverage,
                self._coverage_status,
            ),
            search_missing_topic=self._transitioning(
                "search_missing_topic",
                "discovering",
                self._nodes.search_missing_topic,
                lambda _: "acquiring",
            ),
            generate_final_report=self._transitioning(
                "generate_final_report",
                "reporting",
                self._nodes.generate_final_report,
                lambda _: "completed",
            ),
            complete_research=self._nodes.complete_research,
            fail_durable_work=self._transitioning(
                "fail_durable_work",
                None,
                self._nodes.fail_durable_work,
                lambda _: "failed",
            ),
        )

    @staticmethod
    def _coverage_status(update: ResearchWorkflowState) -> str:
        if update.get("stage") == "awaiting_review":
            return "awaiting_review"
        if update.get("uncovered_topic_ids") and update.get("gap_search_rounds", 0) < 2:
            return "discovering"
        return "reporting"

    def _transitioning(
        self,
        node_name: str,
        required_status: str | None,
        operation: ResearchNode,
        next_status: Callable[[ResearchWorkflowState], str | None],
    ) -> ResearchNode:
        async def run(state: ResearchWorkflowState) -> ResearchWorkflowState:
            before = await self._store.get_run(state["workspace_id"], state["run_id"])
            if before is None:
                raise ResearchWorkflowUnavailable("The research record is unavailable.")
            if required_status is not None and before.status != required_status:
                before = await self._move_status(
                    state, before, required_status, f"{node_name}:resume"
                )
            try:
                update = await operation(state)
            except WORKFLOW_DEPENDENCY_ERRORS as error:
                current = await self._store.get_run(
                    state["workspace_id"], state["run_id"]
                )
                if current is not None and current.status != "failed":
                    failure_state: ResearchWorkflowState = {
                        **state,
                        "failure_code": f"{node_name}_unavailable",
                        "failure_explanation": (
                            "A required local research service is temporarily unavailable."
                        ),
                        "retryable": True,
                    }
                    await self._move_status(
                        failure_state,
                        current,
                        "failed",
                        f"{node_name}:dependency-failed",
                    )
                raise ResearchWorkflowUnavailable(
                    "A required local research service is temporarily unavailable."
                ) from error
            requested_status = next_status(update)
            if requested_status is None or requested_status == before.status:
                return {
                    **update,
                    "canonical_status": before.status,
                    "status_version": before.status_version,
                }
            after = await self._move_status(
                {**state, **update}, before, requested_status, node_name
            )
            return {
                **update,
                "canonical_status": after.status,
                "status_version": after.status_version,
            }

        return run

    async def _move_status(
        self,
        state: ResearchWorkflowState,
        before: ResearchRun,
        requested_status: str,
        transition_name: str,
    ) -> ResearchRun:
        transition_id = uuid5(
                NAMESPACE_URL,
                (
                    f"{UNIFIED_RESEARCH_WORKFLOW_VERSION}:{state['run_id']}:"
                    f"{transition_name}:{before.status_version}:{requested_status}"
                ),
            )
        changed = await self._store.transition_status(
            state["run_id"],
            before.status,
            before.status_version,
            requested_status,
            transition_id,
            f"Unified research graph completed {transition_name}.",
            failed_stage=(before.status if requested_status == "failed" else None),
            failure_code=(state.get("failure_code") if requested_status == "failed" else None),
            failure_explanation=(
                state.get("failure_explanation") if requested_status == "failed" else None
            ),
            retryable=(state.get("retryable", False) if requested_status == "failed" else False),
        )
        after = await self._store.get_run(state["workspace_id"], state["run_id"])
        if after is None:
            raise ResearchWorkflowUnavailable("The research record is unavailable.")
        if not changed and (
            after.status != requested_status
            or after.status_version != before.status_version + 1
        ):
            raise ResearchWorkflowConflict(
                "Official research status changed while the workflow was running."
            )
        return after


def _route_after_coverage(
    state: ResearchWorkflowState,
) -> Literal["search_missing_topic", "generate_final_report", "wait_for_review"]:
    if state.get("stage") == "awaiting_review":
        return "wait_for_review"
    uncovered = state.get("uncovered_topic_ids", [])
    rounds = state.get("gap_search_rounds", 0)
    if uncovered and rounds < MAX_GAP_SEARCH_ROUNDS:
        return "search_missing_topic"
    return "generate_final_report"


def _route_after_acquisition(
    state: ResearchWorkflowState,
) -> Literal["evaluate_relevance", "wait_for_durable_work"]:
    return (
        "wait_for_durable_work"
        if state.get("stage") == "awaiting_preflight"
        else "evaluate_relevance"
    )


def _route_after_summaries(
    state: ResearchWorkflowState,
) -> Literal["assess_topic_coverage", "wait_for_durable_work"]:
    return (
        "wait_for_durable_work"
        if state.get("stage") == "awaiting_summaries"
        else "assess_topic_coverage"
    )


def _route_after_relevance(
    state: ResearchWorkflowState,
) -> Literal["summarize_evidence", "wait_for_review"]:
    return (
        "wait_for_review"
        if state.get("stage") == "awaiting_review"
        else "summarize_evidence"
    )


def build_research_workflow(nodes: ResearchWorkflowNodes) -> StateGraph:
    """Build the single topic-driven research graph without executing it."""

    async def wait_for_review(state: ResearchWorkflowState) -> ResearchWorkflowState:
        resume = interrupt(
            {
                "wait_type": "human_review",
                "workspace_id": str(state["workspace_id"]),
                "research_run_id": str(state["run_id"]),
                "expected_status": state.get("canonical_status", "awaiting_review"),
                "expected_status_version": state.get("status_version", 0),
                "evidence_versions": state.get("review_required_sources", []),
            }
        )
        if not isinstance(resume, dict) or resume.get("outcome") != "accepted":
            raise ResearchWorkflowUnavailable(
                "The human-review continuation outcome is invalid."
            )
        return {"stage": "review_resumed"}

    async def wait_for_durable_work(state: ResearchWorkflowState) -> ResearchWorkflowState:
        wait_stage = state.get("stage")
        resume = interrupt(
            {
                "wait_type": (
                    "candidate_preflight"
                    if wait_stage == "awaiting_preflight"
                    else "evidence_summary"
                ),
                "workspace_id": str(state["workspace_id"]),
                "research_run_id": str(state["run_id"]),
                "expected_status": state.get("canonical_status"),
                "expected_status_version": state.get("status_version", 0),
            }
        )
        if isinstance(resume, dict) and resume.get("outcome") == "failed":
            return {
                "stage": "durable_work_failed",
                "failure_code": "durable_work_failed",
                "failure_explanation": "Required background processing did not complete.",
                "retryable": True,
                "failed_stage": state.get("canonical_status", "acquiring"),
            }
        return {
            "stage": (
                "evidence_acquired"
                if wait_stage == "awaiting_preflight"
                else "summaries_stored"
            )
        }

    graph = StateGraph(ResearchWorkflowState)
    graph.add_node("plan_topics", nodes.plan_topics)
    graph.add_node("search_topics", nodes.search_topics)
    graph.add_node("acquire_evidence", nodes.acquire_evidence)
    graph.add_node("evaluate_relevance", nodes.evaluate_relevance)
    graph.add_node("summarize_evidence", nodes.summarize_evidence)
    graph.add_node("assess_topic_coverage", nodes.assess_topic_coverage)
    graph.add_node("search_missing_topic", nodes.search_missing_topic)
    graph.add_node("generate_final_report", nodes.generate_final_report)
    graph.add_node("complete_research", nodes.complete_research)
    graph.add_node("fail_durable_work", nodes.fail_durable_work)
    graph.add_node("wait_for_review", wait_for_review)
    graph.add_node("wait_for_durable_work", wait_for_durable_work)

    graph.add_edge(START, "plan_topics")
    graph.add_edge("plan_topics", "search_topics")
    graph.add_edge("search_topics", "acquire_evidence")
    graph.add_conditional_edges(
        "acquire_evidence",
        _route_after_acquisition,
        {
            "evaluate_relevance": "evaluate_relevance",
            "wait_for_durable_work": "wait_for_durable_work",
        },
    )
    graph.add_conditional_edges(
        "evaluate_relevance",
        _route_after_relevance,
        {
            "summarize_evidence": "summarize_evidence",
            "wait_for_review": "wait_for_review",
        },
    )
    graph.add_conditional_edges(
        "summarize_evidence",
        _route_after_summaries,
        {
            "assess_topic_coverage": "assess_topic_coverage",
            "wait_for_durable_work": "wait_for_durable_work",
        },
    )
    graph.add_conditional_edges(
        "assess_topic_coverage",
        _route_after_coverage,
        {
            "search_missing_topic": "search_missing_topic",
            "generate_final_report": "generate_final_report",
            "wait_for_review": "wait_for_review",
        },
    )
    graph.add_edge("search_missing_topic", "acquire_evidence")
    graph.add_edge("generate_final_report", "complete_research")
    graph.add_edge("complete_research", END)
    graph.add_edge("wait_for_review", "evaluate_relevance")
    graph.add_conditional_edges(
        "wait_for_durable_work",
        lambda state: state.get("stage"),
        {
            "evidence_acquired": "evaluate_relevance",
            "summaries_stored": "assess_topic_coverage",
            "durable_work_failed": "fail_durable_work",
        },
    )
    graph.add_edge("fail_durable_work", END)
    return graph


def compile_research_workflow(
    nodes: ResearchWorkflowNodes,
    store: ResearchStore,
    checkpointer: AsyncCheckpointSaver,
) -> CompiledResearchGraph:
    """Compile the only production graph with official status and checkpoints."""

    governed = CanonicalResearchWorkflowNodes(nodes, store).wrapped()
    return cast(
        CompiledResearchGraph,
        build_research_workflow(governed).compile(checkpointer=checkpointer),
    )


async def _run_checkpoint_maintenance(action: str, limit: int) -> int:
    """Run one bounded local checkpoint-maintenance batch."""

    settings = get_settings()
    store = ResearchStore(settings.database_url)
    lifecycle = ResearchCheckpointLifecycle(settings.database_url, store)
    try:
        await lifecycle.start()
        if action == "retry-terminal-cleanup":
            return await lifecycle.retry_completed_cleanup(limit)
        return await lifecycle.delete_obsolete_threads(limit)
    finally:
        await lifecycle.stop()


async def _run_obsolete_state_cleanup(limit: int) -> int:
    """Remove only state owned by the retired standalone workflow."""

    from app.agent_runtime.store import RuntimeStore
    from app.agentic_research.store import AgenticResearchStore

    settings = get_settings()
    runtime_store = RuntimeStore(settings.database_url)
    agentic_store = AgenticResearchStore(settings.database_url)
    try:
        deleted = await runtime_store.delete_obsolete_workflow_records(limit)
        await agentic_store.remove_obsolete_control_tables()
        return deleted
    finally:
        await runtime_store.close()
        await agentic_store.close()


def checkpoint_maintenance_main() -> None:
    """Provide a bounded operator command without direct checkpoint-table SQL."""

    parser = argparse.ArgumentParser(description="Maintain research graph checkpoints.")
    parser.add_argument(
        "action",
        choices=(
            "retry-terminal-cleanup",
            "delete-obsolete-threads",
            "delete-obsolete-runtime-records",
        ),
    )
    parser.add_argument("--limit", type=int, default=100)
    arguments = parser.parse_args()
    if not 1 <= arguments.limit <= 1000:
        parser.error("--limit must be between 1 and 1000")
    if arguments.action == "delete-obsolete-runtime-records":
        result = asyncio.run(_run_obsolete_state_cleanup(arguments.limit))
    else:
        result = asyncio.run(
            _run_checkpoint_maintenance(arguments.action, arguments.limit)
        )
    print(result)


if __name__ == "__main__":
    checkpoint_maintenance_main()
