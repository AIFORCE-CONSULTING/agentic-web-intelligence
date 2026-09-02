# ADR 0005: Define a governed agent-runtime contract before adding agents

- Status: Accepted
- Date: 2026-08-31

## Context

Phase 2 delivers a governed, evidence-producing web-research workflow. Phase
3 introduces planning, memory, and multiple collaborating agent roles. Without
an explicit runtime contract, those additions could turn model output into
authority, create hidden tool paths, lose execution provenance, or make
failures unsafe to resume.

The platform needs reusable agent patterns while preserving the FastAPI,
runtime, and MCP policy boundaries established by ADRs 0002 through 0004.

## Decision

Adopt the Phase 3 agent-runtime contract in
[Agent runtime contract](../agent-runtime.md).

The runtime will:

- use explicit orchestrator, planner, specialist, reviewer, and human-operator
  roles with bounded responsibilities;
- model work as a versioned plan of typed steps, each with an identity,
  declared capability, retry budget, timeout, and idempotency key;
- record run lifecycle changes, handoffs, approvals, policy outcomes, tool
  calls, and terminal outcomes as attributable audit events;
- treat plans, retrieved material, tool results, and inter-agent messages as
  untrusted data, not as authority or executable instructions;
- require explicit, validated handoffs with no privilege escalation;
- persist resumable state and audit history durably in PostgreSQL, using Redis
  only for ephemeral coordination and object storage for large immutable
  artifacts when needed; and
- retain the MCP host as the sole tool boundary. Agents may request approved
  capabilities but cannot call providers or MCP servers directly.

Runs use explicit terminal states and classify failures. The runtime retries
only declared transient work with the same idempotency key. Policy failures,
validation failures, and ambiguous effects require an authorized change or
human attention rather than an automatic retry.

## Consequences

LangGraph can be introduced as the workflow implementation without making its
internal graph shape the platform contract. A single-process implementation can
begin with all roles as graph nodes and later distribute them without changing
authorization or audit semantics.

The initial Phase 3 work has more schema and event-recording overhead than a
free-form autonomous-agent prototype. In return, operators can inspect what
was planned, who performed each step, what policy allowed, and whether a run
can safely resume.

Persistent user memory, tenant isolation, enterprise identity, write tools,
and human approval UX remain subsequent scoped deliverables. They must not be
implied by this runtime contract.
