<!--
Sync Impact Report
- Version change: 1.1.0 -> 1.2.0
- Modified principle: One owner for each responsibility -> One owner for each
  responsibility, business decision, and workflow state.
- Expanded sections: Required Specification and Design Workflow; Quality Gates;
  Governance.
- Templates updated: .specify/templates/plan-template.md,
  .specify/templates/spec-template.md, .specify/templates/tasks-template.md.
- Runtime guidance updated: AGENTS.md.
- Published constitution page: docs/architecture-constitution.md includes this
  canonical file and requires no duplicate edit.
- Deferred follow-up: the active 001-consolidate-research-architecture feature
  artifacts must be revised against the new ownership matrix before implementation.
-->
# Agentic Web Intelligence Constitution

This constitution keeps the platform coherent as its agentic capabilities grow.
It applies to human contributors and coding agents. Architecture work begins by
understanding the system that already exists, not by treating a roadmap item as
an isolated request for new code.

## Core Principles

### I. One owner for each responsibility, decision, and state

Every platform responsibility MUST have one canonical owner. A change MUST
identify that owner before implementation. New code may extend or adapt the
owner, but MUST NOT create a second source of authority for the same
responsibility.

Naming a component is not enough. Every durable or externally visible business
decision and workflow state MUST identify:

- its business meaning and the question it answers;
- the specific canonical record and field that holds the official answer;
- the single component authorized to write it;
- the components permitted to read it;
- any checkpoints, caches, histories, or other derived copies;
- the complete allowed state transitions and their guards; and
- the rule used to resolve stale, conflicting, or concurrently written values.

If two records can answer the same business question, one MUST be declared
authoritative and the other MUST be explicitly classified as derived or
operational. A LangGraph checkpoint is an execution bookmark, and Temporal
history describes durable execution; neither becomes official business state
unless this constitution is amended to assign that responsibility explicitly.

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
   callers, stores, workflows, workers, and external boundaries. Complete a
   State and Decision Ownership Matrix for every business decision and workflow
   state touched by the change.
3. **Plan:** Write `plan.md` showing what is reused, extended, migrated, retired,
   or explicitly excluded. Complete the Constitution Check before research and
   re-check it after design. The plan MUST NOT pass while an ownership row,
   workflow transition, or conflict-resolution rule remains unresolved.
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

Every qualifying plan MUST contain this matrix with concrete values:

| Required field | Required answer |
| --- | --- |
| State or decision | The named state or decision being governed |
| Business question | The question for which this is the official answer |
| Canonical record | The exact persisted record and field, not merely a database name |
| Authorized writer | The one component permitted to change the official answer |
| Readers | Components that may consume the official answer |
| Derived copies | Checkpoints, histories, caches, or views that repeat it |
| Allowed transitions | Complete starting, waiting, terminal, and failure transitions |
| Conflict resolution | Which value wins and how disagreement is repaired or surfaced |

For workflows, the plan MUST also state which canonical value the user
interface displays, which value authorization evaluates, how interrupted work
resumes, and how retries and concurrent requests avoid invalid or duplicate
transitions. Broad answers such as "PostgreSQL owns state" do not satisfy this
requirement.

## Quality Gates

- Every plan MUST identify the trigger, authority owner, canonical state,
  direct-or-durable execution rule, human-decision record, and excluded callers
  or capabilities.
- Every business decision and workflow state MUST have one canonical record,
  one authorized writer, complete transitions, and an explicit reconciliation
  rule for every derived copy.
- A Constitution Check MUST fail while material ownership, transition,
  continuation, dependency-failure, or conflict-resolution questions remain
  open. Such questions MUST NOT be disguised as implementation tasks.
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
code review MUST verify compliance. Later analysis supplements these gates; it
does not excuse an incomplete specification or plan. Any approved exception
MUST be documented in the plan's Complexity Tracking table with the rejected
simpler alternative and a retirement or review condition.

**Version**: 1.2.0 | **Ratified**: 2026-09-24 | **Last Amended**: 2026-09-26
