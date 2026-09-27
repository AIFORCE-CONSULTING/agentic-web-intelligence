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
class WorkflowContinuationEnvelope:
    """Typed request to resume a graph after a durable result has been persisted."""

    wait: DurableWait
    result_record_id: str
    outcome: Literal["completed", "failed"]


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
