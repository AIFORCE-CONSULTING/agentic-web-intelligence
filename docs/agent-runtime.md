# Agent runtime contract

Phase 3 introduces a governed runtime for planning and coordinating agent work.
It extends the Phase 2 research workflow; it does not create an alternate path
to tools, providers, or enterprise systems.

## Runtime invariants

- Every external effect is performed through a platform capability exposed by
  the MCP host or a future equivalently governed service boundary.
- An agent may propose a plan, but policy determines whether a step may run.
- The runtime treats tool output, retrieved content, and inter-agent messages
  as untrusted data. They cannot alter the requested goal, authority, or tool
  policy.
- Every run, step, handoff, policy decision, tool call, and terminal outcome is
  attributable to an authenticated request and has a correlation ID.
- A failed or interrupted run is resumable only from persisted, validated
  checkpoints. It never repeats an effectful step implicitly.

## Roles

The initial runtime uses explicit roles rather than general-purpose agents.

| Role | Responsibility | May do | Must not do |
| --- | --- | --- | --- |
| Orchestrator | Own the run lifecycle and state transitions. | Start, cancel, resume, and route work. | Invent a goal or bypass policy. |
| Planner | Translate the approved goal into a bounded, ordered plan. | Propose steps and required capabilities. | Invoke tools or approve its own plan. |
| Specialist | Perform one assigned, typed unit of work. | Request approved capabilities through the runtime. | Delegate outside the declared plan or alter its scope. |
| Reviewer | Evaluate completeness, provenance, and policy-relevant output. | Accept, reject, or request a bounded retry. | Modify evidence or execute tools. |
| Human operator | Retains authority for approvals, cancellations, and escalations. | Approve governed gates and inspect execution. | Be silently impersonated by a model. |

An initial implementation may run the planner, specialist, and reviewer as
nodes in one LangGraph graph. Role separation remains a contract even when the
nodes share a model or process.

## State model

A run has immutable request metadata and an append-only event history. Its
current state is a materialized view of that history.

```text
requested -> planning -> awaiting_approval -> executing -> reviewing -> completed
                    |                         |              |
                    +-> rejected              +-> failed     +-> needs_attention
                                              +-> cancelled
```

Each plan step has a stable ID, assigned role, declared capability, input and
output schema versions, attempt count, idempotency key, timeout, and terminal
status. The runtime persists only validated, typed state; free-form model
messages are retained as auditable artifacts, never as executable state.

## Handoffs

A handoff is an explicit event from one role to another. It contains only:

- the run and plan-step IDs;
- the approved goal and bounded assignment;
- references to validated inputs and evidence, rather than copied secrets or
  unbounded page content;
- the required output schema, deadline, and capability constraints.

The receiving role validates the handoff against the plan and current policy.
It can accept it, reject it with a typed reason, or request human attention.
No role may issue an untracked handoff or grant another role broader authority.

## Failure and recovery

Failures are classified as validation, policy, dependency, timeout, model,
or unexpected-runtime failures. The runtime records the classification,
sanitized diagnostic information, affected step, and correlation ID.

- Validation and policy failures are terminal for that attempted step; they
  require a changed, authorized input or plan.
- Transient dependency failures may retry only within the plan's explicit
  retry budget and with the same idempotency key.
- Timeouts cancel the active work and require checkpoint validation before any
  resume.
- Ambiguous effects become `needs_attention`; the runtime does not retry them
  automatically.
- Cancellation is cooperative, records a terminal event, and prevents new
  handoffs or tool calls.

## Persistence boundaries

PostgreSQL is the durable source of truth for run metadata, plans, typed state,
handoffs, approvals, audit events, and provenance references. Object storage,
when introduced, holds larger immutable artifacts such as normalized evidence
or model outputs; the database holds their hashes and references. Redis may be
used only for ephemeral coordination, caching, and rate limiting, never as the
sole record needed to resume a run.

The runtime does not persist provider credentials, raw authentication headers,
or secrets in graph state, prompts, handoffs, or audit events. It minimizes
stored personal data, applies retention rules by artifact type, and scopes
access by tenant/workspace once Phase 4 identity controls are introduced.

## Compatibility with Phase 2

The Phase 2 MCP host remains the sole endpoint for `web.search` and
`web.extract`. Phase 3 adds structured plans and runtime events around those
calls; it does not expand the tool allowlist, web permissions, or MCP policy.
New capabilities require their own policy contract and ADR before agents can
use them.

## Initial implementation

The first Phase 3 runtime slice persists runs, server-assigned planner steps,
and append-only lifecycle events in PostgreSQL. It exposes no public runtime
mutation endpoint: creating runs, assigning roles and capabilities, changing
state, and creating handoffs are runtime-internal actions. Read-only inspection
is available through `GET /v1/runtime/runs` and `GET /v1/runtime/runs/{run_id}`.

This means a model, browser client, or crafted request cannot create a new run,
claim a role, or add a capability by placing fields in a message or JSON
payload. A future authenticated operator control plane will have its own
identity and authorization boundary; it must not reuse an agent-facing tool or
token.

## Server-only runtime service

`RuntimeService` is the only application component that turns a proposed plan
into runtime assignments. It is a dependency of the FastAPI application, but
is deliberately neither an HTTP route nor an MCP tool.

Its version-controlled policy gives researchers exactly `web.search` and
`web.extract`, and reviewers no capabilities. A plan must contain one to five
researcher steps followed by exactly one reviewer step. Handoffs are allowed
only from planner to researcher and from researcher to reviewer. The service
checks stored step identities and roles before recording a handoff; handoff
content cannot broaden the recipient's authority.

## Deterministic planner

The first planner is a server-only LangGraph workflow. Given an internally
approved goal, it creates a fixed plan of one researcher step and one reviewer
step, then stops in `awaiting_approval`. It does not invoke an LLM, call MCP
tools, execute a plan, or bypass the future operator approval gate.

This establishes the orchestration path before introducing model-generated
plans. A later planner may propose bounded steps, but the runtime service will
continue to materialize only the roles, capabilities, and handoff paths allowed
by its version-controlled policy.

## Deterministic executor

After the runtime approval gate, the server-only executor activates the stored
researcher step and calls the existing MCP host internally. It first calls
`web.search` using the approved goal, then calls `web.extract` only for the
first governed search result. Before each call, the runtime checks the stored
capability grant for that exact researcher step. It records only bounded result
metadata in the runtime event stream and ends in `reviewing`; a failed or
denied execution ends in `failed` without an implicit retry.

The executor does not expose a public trigger, add a new MCP tool, run a
reviewer, or give the reviewer feedback capabilities.

## Deferred multi-agent refinement

Reviewer prompts, structured review decisions, and a bounded reviewer-to-
researcher revision loop are recorded for the later Phase 3 multi-agent work.
They are not part of the deterministic planner slice. If added, they must use
typed review outcomes, preserve the researcher's existing capabilities, enforce
a retry budget, and route exhausted reviews to `needs_attention`.
