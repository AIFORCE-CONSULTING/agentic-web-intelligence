# Architecture Constitution

This constitution keeps the platform coherent as its agentic capabilities grow.
It applies to human contributors and coding agents. Architecture work begins by
understanding the system that already exists, not by treating a roadmap item as
an isolated request for new code.

## One owner for each responsibility

Every platform responsibility has one canonical owner. A change must identify
that owner before implementation. New code may extend or adapt the owner, but it
must not create a second source of authority for the same responsibility.

The current foundational ownership boundaries are:

| Responsibility | Canonical owner |
| --- | --- |
| Application and agent workflow orchestration | The existing LangGraph runtime and its governed `RuntimeService` |
| Durable execution, retry and recovery | Temporal through the platform's durable-execution boundaries |
| Official business and audit state | PostgreSQL through the owning service stores |
| Agent-visible web capabilities | The code-owned MCP registry and governed MCP host |
| Web evidence eligibility | The local web-trust service and its versioned policy |
| Human evidence acceptance | The existing evidence-review service and persisted acceptance record |
| Source summaries and keywords | The evidence-summary service and store |
| Meaning-based research decisions | The selected local model behind versioned prompts and validated contracts |

Changing one of these owners requires an approved ADR amendment or replacement.

## Extend before creating

Before adding a service, workflow, state machine, store, tool, or policy layer,
review the existing code, ADRs, routes, workers, dependencies, and tests for that
responsibility. Prefer extending the established component. A new component is
appropriate only when it has a distinct responsibility that cannot reasonably
belong to the existing owner.

Roadmap verbs such as “add,” “build,” or “connect” do not authorize a parallel
implementation.

## Selected orchestration and execution foundations

LangGraph, from the LangChain ecosystem, is the canonical framework for
application and agent workflow orchestration. Deterministic Python code remains
appropriate inside graph nodes for validation, counters, limits, normalization,
and policy enforcement. It must not become a competing workflow engine.

Temporal is the canonical durable-execution system. LangGraph describes the
application workflow; Temporal makes qualifying work durable and recoverable.
Neither replaces the other, and models and operators do not choose between them.

PostgreSQL is the official record of business state. LangGraph state carries the
bounded working context needed to execute a workflow, but it is not a competing
permanent record.

## Models propose and the platform authorizes

Models may perform approved meaning-based work and propose typed actions. They do
not grant capabilities, approve evidence, alter policy, write arbitrary records,
choose execution infrastructure, or declare that validation succeeded. Existing
platform services retain those decisions.

## Replacement includes retirement

A replacement design is incomplete unless it identifies:

- the overlapping implementation;
- every caller and worker that still uses it;
- the stored state that must remain readable or be migrated;
- the tests and documentation that must change; and
- the condition under which the old path can be removed.

Do not leave two active paths indefinitely under the label of backward
compatibility.

## Required design review sequence

Before implementation, present the architecture reconciliation required by
`AGENTS.md`. After that reconciliation is accepted, present the operational
design checkpoint covering the trigger, authority, canonical state, direct or
durable execution, human decisions, and excluded callers or capabilities.

Tests must verify integration through the canonical owners, not only that a new
component works in isolation. A pull request confirms the agreed design; it does
not replace design review.
