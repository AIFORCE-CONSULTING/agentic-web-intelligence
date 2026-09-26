<!--
Sync Impact Report
- Version change: initial Specify template -> 1.1.0
- Existing principles incorporated: canonical ownership, extend before creating,
  selected frameworks, platform authorization, and complete retirement.
- Added principle: specifications preserve architecture.
- Added sections: Required Specification and Design Workflow; Quality Gates.
- Templates updated: plan-template.md, spec-template.md, tasks-template.md.
- Runtime guidance updated: AGENTS.md and the published constitution page.
- Deferred items: none.
-->
# Agentic Web Intelligence Constitution

This constitution keeps the platform coherent as its agentic capabilities grow.
It applies to human contributors and coding agents. Architecture work begins by
understanding the system that already exists, not by treating a roadmap item as
an isolated request for new code.

## Core Principles

### I. One owner for each responsibility

Every platform responsibility MUST have one canonical owner. A change MUST
identify that owner before implementation. New code may extend or adapt the
owner, but MUST NOT create a second source of authority for the same
responsibility.

| Responsibility | Canonical owner |
| --- | --- |
| Application and agent workflow orchestration | LangGraph coordinated through the governed `RuntimeService` |
| Agent roles, capabilities, human gates, and authority decisions | `RuntimeService` and its canonical PostgreSQL records |
| Durable execution, retry, and recovery | Temporal through the platform's durable-execution boundaries |
| Official business and audit state | PostgreSQL through the owning service stores |
| Agent-visible web capabilities | The code-owned MCP registry and governed MCP host |
| Web evidence eligibility | The local web-trust service and its versioned policy |
| Human evidence acceptance | The evidence-review service and persisted acceptance record |
| Source summaries and keywords | The evidence-summary service and store |
| Meaning-based research decisions | The selected local model behind versioned prompts and validated contracts |

Changing one of these owners requires explicit user approval and an ADR
amendment or replacement.

### II. Extend before creating

Before adding a service, workflow, state machine, store, tool, or policy layer,
the specification and plan MUST review the existing code, ADRs, routes, workers,
dependencies, stores, and tests for that responsibility. The established owner
MUST be extended unless a distinct responsibility cannot reasonably belong to
it and the user approves a new boundary.

Roadmap verbs such as "add," "build," or "connect" do not authorize a parallel
implementation.

### III. Use the selected orchestration and execution foundations

LangGraph is the canonical framework for application and agent workflow
coordination. Deterministic Python remains appropriate inside graph nodes for
validation, counters, limits, normalization, and policy enforcement, but MUST
NOT become a competing workflow engine.

`RuntimeService` is the canonical authority boundary. LangGraph may request an
action, but it MUST NOT supply or expand its own capability grant.

Temporal is the canonical durable-execution system. LangGraph describes the
application sequence; Temporal makes qualifying work durable and recoverable.
Models and operators MUST NOT choose between direct and durable execution.

PostgreSQL is the official business and audit record. LangGraph state carries
bounded execution context and MUST NOT become a competing permanent store.

### IV. Models propose and the platform authorizes

Models may perform approved meaning-based work and propose typed actions. They
MUST NOT grant capabilities, approve evidence, alter policy, write arbitrary
records, choose execution infrastructure, or declare that validation succeeded.

Trusted platform code MUST validate every proposal against canonical stored
identity, role, task, capability, resource, policy, limits, and current state.
Every unspecified capability is denied. Human-only decisions MUST be recorded
with the human identity and enforced independently of LangGraph and Temporal.

### V. Replacement includes retirement

A replacement design is incomplete unless it identifies:

- the overlapping implementation;
- every route, service, worker, and workflow that still calls it;
- stored state that must remain readable or be migrated;
- tests and documentation that must change; and
- the verified condition under which the old path can be removed.

The platform MUST NOT leave two active paths indefinitely under the label of
backward compatibility.

### VI. Specifications preserve architecture

Significant features, workflow changes, authority changes, background work,
human approvals, durable execution, and external side effects MUST begin with a
Specify specification before implementation.

Specifications MUST be understandable to a non-technical stakeholder and state
the business problem, actors, desired outcomes, scope, exclusions, acceptance
scenarios, and measurable success criteria. They MUST identify any human-only
decision or agent limitation that is part of the product requirement.

Implementation plans MUST then reconcile the specification with the current
architecture. A specification describes what the platform must accomplish; it
does not silently select a new service, authority, store, framework, or workflow
owner.

## Required Specification and Design Workflow

Work governed by Principle VI follows this sequence:

1. **Specify:** Write and review `spec.md` in business language. Resolve material
   ambiguity before implementation planning.
2. **Reconcile:** Inspect current code and ADRs. Identify existing owners,
   callers, stores, workflows, workers, and external boundaries.
3. **Plan:** Write `plan.md` showing what is reused, extended, migrated, retired,
   or explicitly excluded. Complete the Constitution Check before research and
   re-check it after design.
4. **Approve architecture:** Present the architecture reconciliation and the
   operational checkpoint required by `AGENTS.md`. Runtime or workflow code MUST
   NOT change before explicit approval.
5. **Task:** Generate traceable tasks from the approved specification and plan.
   Tasks MUST include migration, tests, documentation, and retirement work when
   applicable.
6. **Analyze:** Check consistency among the specification, plan, tasks, ADRs,
   roadmap, and constitution before implementation.
7. **Implement and verify:** Make the smallest coherent change, run risk-scaled
   tests, and update architecture records before declaring the work complete.

The architecture diagram, glossary, ADRs, and roadmap are inputs to this
process. Specify artifacts do not override accepted ADRs or canonical ownership
boundaries.

## Quality Gates

- Every plan MUST identify the trigger, authority owner, canonical state,
  direct-or-durable execution rule, human-decision record, and excluded callers
  or capabilities.
- Authority and workflow changes MUST include default-deny, wrong-workspace,
  wrong-run, invalid-state, malformed-input, and retry/idempotency tests as
  applicable.
- Integration tests MUST exercise canonical owners rather than only isolated
  replacement components.
- Model output MUST remain untrusted until validated by deterministic platform
  contracts.
- Documentation and diagrams MUST describe the code that actually runs.
- A pull request verifies an approved design; it MUST NOT serve as the first
  architecture review gate.

## Governance

This file is the canonical project constitution. The published
`docs/architecture-constitution.md` page includes this file so the repository
has one source of constitutional authority.

Amendments require explicit user approval, a Sync Impact Report, propagation to
dependent Specify templates and runtime guidance, and semantic versioning:

- MAJOR for incompatible removals or redefinitions of governance principles;
- MINOR for a new principle or materially expanded governance; and
- PATCH for clarifications that do not alter obligations.

Every specification, implementation plan, task list, architecture review, and
code review MUST verify compliance. Any approved exception MUST be documented in
the plan's Complexity Tracking table with the rejected simpler alternative and
a retirement or review condition.

**Version**: 1.1.0 | **Ratified**: 2026-09-24 | **Last Amended**: 2026-09-26
