"""Typed public contract for the deterministic agent runtime core."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

RuntimeRole = Literal["orchestrator", "planner", "researcher", "reviewer"]
RuntimeCapability = Literal["web.search", "web.extract"]
RunStatus = Literal[
    "requested",
    "planning",
    "awaiting_approval",
    "executing",
    "reviewing",
    "completed",
    "rejected",
    "failed",
    "cancelled",
    "needs_attention",
]
StepStatus = Literal["pending", "active", "completed", "failed", "cancelled", "needs_attention"]


class RuntimeRunRequest(BaseModel):
    """Create a runtime run; role and capability grants are server-owned."""

    model_config = ConfigDict(extra="forbid")

    goal: str = Field(min_length=1, max_length=512)


class RuntimeTransitionRequest(BaseModel):
    """A requested state change that the runtime validates against its state machine."""

    model_config = ConfigDict(extra="forbid")

    status: RunStatus


class RuntimeHandoffRequest(BaseModel):
    """Untrusted content for a server-validated handoff to an existing plan step."""

    model_config = ConfigDict(extra="forbid")

    recipient_step_id: UUID
    content: str = Field(min_length=1, max_length=8_000)


class PlanStepProposal(BaseModel):
    """Untrusted plan content; it deliberately cannot request capabilities."""

    model_config = ConfigDict(extra="forbid")

    role: Literal["researcher", "reviewer"]
    title: str = Field(min_length=1, max_length=512)


class ApprovedPlanStep(BaseModel):
    """A runtime-owned assignment produced after proposal validation."""

    id: UUID
    role: RuntimeRole
    title: str
    allowed_capabilities: list[RuntimeCapability] = Field(default_factory=list)
    idempotency_key: str
    timeout_seconds: int = Field(gt=0)


class RuntimeEvent(BaseModel):
    """An append-only runtime decision or outcome."""

    event_type: str
    occurred_at: datetime
    details: dict[str, object] = Field(default_factory=dict)


class RuntimeStep(BaseModel):
    """A server-assigned unit of work with immutable role and capability grants."""

    id: UUID
    role: RuntimeRole
    title: str
    status: StepStatus
    allowed_capabilities: list[RuntimeCapability] = Field(default_factory=list)
    attempt_count: int = Field(ge=0)
    idempotency_key: str
    timeout_seconds: int = Field(gt=0)
    created_at: datetime
    updated_at: datetime


class RuntimeHandoff(BaseModel):
    """A runtime-created record that links a bounded assignment to its recipient."""

    id: UUID
    sender_step_id: UUID
    recipient_step_id: UUID
    content: str
    created_at: datetime


class RuntimeRun(BaseModel):
    """Inspectable materialized state for one governed runtime execution."""

    id: UUID
    goal: str
    status: RunStatus
    created_at: datetime
    updated_at: datetime
    steps: list[RuntimeStep] = Field(default_factory=list)
    handoffs: list[RuntimeHandoff] = Field(default_factory=list)
    events: list[RuntimeEvent] = Field(default_factory=list)


class RuntimeRunSummary(BaseModel):
    """Bounded runtime list entry for operator inspection."""

    id: UUID
    goal: str
    status: RunStatus
    created_at: datetime
    updated_at: datetime
    step_count: int = Field(ge=0)


class RuntimeRunList(BaseModel):
    """Recent governed runtime executions."""

    runs: list[RuntimeRunSummary]


class RuntimeStoreUnavailable(RuntimeError):
    """Raised when the durable runtime store cannot be reached."""
