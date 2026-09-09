# ADR 0013: Keep durable execution subordinate to runtime policy

- Status: Accepted
- Date: 2026-09-08

## Context

Phase 3 established a server-only runtime that owns plans, role assignments,
capability grants, state transitions, and bounded researcher-reviewer
handoffs. Its work currently runs within an API process. That is appropriate
for short, deterministic work, but it cannot safely survive an API restart or
give operators reliable control over long-running execution. Human decisions
remain runtime-owned whether the resulting work is short or durable.

Phase 5 will introduce a durable workflow engine, initially Temporal. A
workflow engine can retry and resume work, but it must not become an alternate
control plane through which an agent, workflow input, or worker can create a
new goal, role, capability, or tool path.

## Decision

The platform's runtime service remains the authority boundary. The durable
workflow engine is a server-only execution and scheduling mechanism, not an
agent tool, public API, identity provider, or policy engine.

### Eligible work

Only an existing runtime run with a server-materialized plan may outlive its
initiating API request. The first durable workflow may execute an approved
researcher step, persist a validated checkpoint, and run the no-tool reviewer.
Human approval and revision gates are runtime-owned control-plane state, not
Temporal behavior. Planning, plan approval, role assignment, capability grants,
and creation of a durable workflow remain trusted server-side actions.

The runtime records a human approval or rejection in PostgreSQL for an
approval-gated plan. A short execution can consume that decision directly. If
trusted platform code determines that the work needs durability, it can then
schedule the one fixed Temporal workflow using the stored approval as a
precondition. An approval decision does not start, signal, configure, or
otherwise depend on Temporal. The platform never relies on an open browser
request, a model response, or a worker's in-memory state as the source of truth
for a running job.

### Authority and inputs

Each scheduled workflow receives a versioned, immutable execution envelope
containing only the runtime run ID, workspace ID, approved plan/step IDs,
policy version, idempotency identities, and bounded deadline information. It
does not receive credentials, browser sessions, raw request headers, or
agent-authored authority fields.

Before every activity that can call a governed capability, the worker reloads
the persisted run and asks the runtime service to validate the stored step,
current state, workspace, and capability grant. Workflow input, activity
results, retrieved content, and handoff text remain untrusted data. They cannot
alter the goal, add a role, select a tool, expand a capability, or schedule new
work outside the approved plan.

Temporal credentials, when introduced, belong only to the platform's
server-side deployment. Neither an agent nor an MCP client receives a Temporal
client, task queue name, or generic workflow-start capability.

### Retry, timeout, and idempotency

- A step's existing server-assigned timeout is the maximum work time. A durable
  workflow has a separate overall deadline and stops at that deadline even if
  individual activity attempts remain.
- Only dependency failures explicitly classified as transient may retry.
  Validation, policy, authorization, schema, and configuration failures never
  retry automatically.
- Every retry uses the same persisted step idempotency key. Activities must
  record their attempt and check for a prior completed effect before repeating
  it.
- Any effect whose completion is ambiguous is not retried. The run becomes
  `needs_attention` with sanitized diagnostic metadata.
- The existing researcher revision limit is a review-loop budget, not a
  generic activity retry budget. Durable retries do not create additional
  reviewer-to-researcher revisions.

### Cancellation, retention, and escalation

An authenticated operator may request cancellation through a future
authorization-protected control-plane endpoint. Cancellation is recorded in
the runtime store, delivered to the workflow cooperatively, and prevents new
activities, handoffs, or capability calls. A worker rechecks cancellation at
each checkpoint; cancellation does not erase existing audit history.

The durable engine's execution history is operational data, not the canonical
record of the run. PostgreSQL remains the durable system of record for runtime
state, approvals, events, handoffs, and provenance references. Run-scoped
memory continues to expire after 24 hours. The Phase 5 implementation will
add a documented retention schedule for durable workflow metadata and cleanup
jobs; it will not extend retention implicitly or retain secrets, raw provider
responses, or browser credentials.

Exhausted transient retries, expired deadlines, unavailable dependencies,
ambiguous effects, and rejected approval gates transition to a typed terminal
or `needs_attention` state. They create a minimal, redacted audit event and
require an authorized operator decision to retry, revise, cancel, or close the
run. No durable workflow may silently restart a terminal run.

## Consequences

Phase 5 can add resilient execution and runtime-owned human decision state
without weakening the Phase 3 runtime contract or the Phase 4 workspace
authorization boundary.
It also requires more explicit state, idempotency, activity classification,
and operator controls than a background-task implementation.

The next implementation slice is a local Temporal deployment and a narrow
server-only adapter that executes one already-approved runtime path. Public
workflow-start endpoints, agent-accessible scheduler tools, arbitrary worker
code, and automatic retries of uncertain effects are explicitly out of scope.
