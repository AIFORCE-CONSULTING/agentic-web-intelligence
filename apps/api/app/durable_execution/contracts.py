"""Typed, non-authoritative inputs and outputs for durable runtime work."""

from dataclasses import dataclass
from typing import Literal

DURABLE_POLICY_VERSION = "phase-5-v1"


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
