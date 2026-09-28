"""Typed, non-authoritative inputs and outputs for durable runtime work."""

from dataclasses import dataclass
from typing import Literal

DURABLE_POLICY_VERSION = "phase-5-v1"
UNIFIED_RESEARCH_WORKFLOW_VERSION = "unified-research:v1"


@dataclass(frozen=True)
class WorkflowThreadReference:
    """Stable identity for the one resumable graph associated with a research task."""

    research_run_id: str
    workspace_id: str
    thread_id: str
    checkpoint_namespace: str = UNIFIED_RESEARCH_WORKFLOW_VERSION


@dataclass(frozen=True)
class DurableWait:
    """Bounded bookmark recorded when the graph delegates qualifying durable work."""

    thread: WorkflowThreadReference
    execution_id: str
    wait_type: Literal["candidate_preflight", "evidence_summary"]
    expected_research_status: str
    expected_status_version: int
    idempotency_key: str


@dataclass(frozen=True)
class WorkflowContinuationContext:
    """Graph-owned facts used to create one durable wait bookmark."""

    thread: WorkflowThreadReference
    expected_research_status: str
    expected_status_version: int

    def wait(
        self,
        execution_id: str,
        wait_type: Literal["candidate_preflight", "evidence_summary"],
    ) -> DurableWait:
        return DurableWait(
            thread=self.thread,
            execution_id=execution_id,
            wait_type=wait_type,
            expected_research_status=self.expected_research_status,
            expected_status_version=self.expected_status_version,
            idempotency_key=(
                f"{self.thread.checkpoint_namespace}:{wait_type}:{execution_id}:"
                f"{self.expected_status_version}"
            ),
        )


@dataclass(frozen=True)
class WorkflowContinuationEnvelope:
    """Typed request to resume a graph after a durable result has been persisted."""

    wait: DurableWait
    result_record_id: str
    outcome: Literal["completed", "failed"]


@dataclass(frozen=True)
class CandidatePreflightWorkflowInput:
    """Stored preflight request plus its non-authoritative graph bookmark."""

    request_json: str
    continuation: WorkflowContinuationEnvelope


@dataclass(frozen=True)
class EvidenceSummaryWorkflowInput:
    """Stored summary execution identity plus its graph bookmark."""

    execution_id: str
    continuation: WorkflowContinuationEnvelope


@dataclass(frozen=True)
class RuntimeExecutionEnvelope:
    """Identifiers copied from an already approved server-owned runtime run."""

    run_id: str
    workspace_id: str
    policy_version: str


@dataclass(frozen=True)
class DurableExecutionResult:
    """Bounded workflow result; durable history never carries tool output."""

    run_id: str
    status: Literal["completed", "failed", "needs_attention", "cancelled"]
