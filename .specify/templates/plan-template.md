# Implementation Plan: [FEATURE]

**Branch**: `[###-feature-name]` | **Date**: [DATE] | **Spec**: [link]
**Input**: Feature specification from `/specs/[###-feature-name]/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

[Extract from feature spec: primary requirement + technical approach from research]

## Technical Context

<!--
  ACTION REQUIRED: Replace the content in this section with the technical details
  for the project. The structure here is presented in advisory capacity to guide
  the iteration process.
-->

**Language/Version**: [e.g., Python 3.11, Swift 5.9, Rust 1.75 or NEEDS CLARIFICATION]  
**Primary Dependencies**: [e.g., FastAPI, UIKit, LLVM or NEEDS CLARIFICATION]  
**Storage**: [if applicable, e.g., PostgreSQL, CoreData, files or N/A]  
**Testing**: [e.g., pytest, XCTest, cargo test or NEEDS CLARIFICATION]  
**Target Platform**: [e.g., Linux server, iOS 15+, WASM or NEEDS CLARIFICATION]
**Project Type**: [e.g., library/cli/web-service/mobile-app/compiler/desktop-app or NEEDS CLARIFICATION]  
**Performance Goals**: [domain-specific, e.g., 1000 req/s, 10k lines/sec, 60 fps or NEEDS CLARIFICATION]  
**Constraints**: [domain-specific, e.g., <200ms p95, <100MB memory, offline-capable or NEEDS CLARIFICATION]  
**Scale/Scope**: [domain-specific, e.g., 10k users, 1M LOC, 50 screens or NEEDS CLARIFICATION]

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Canonical owner:** Identify the existing owner of every responsibility this
  change touches and cite the relevant code and ADRs.
- **State and decision ownership:** Complete the mandatory matrix below for
  every business decision and workflow state. Name the exact canonical record
  and field, not only the database or service.
- **No parallel authority:** Confirm the plan does not add a competing workflow,
  state machine, policy authority, store, or execution path.
- **Selected foundations:** Explain how LangGraph coordinates the workflow, how
  RuntimeService authorizes agent actions, when Temporal supplies durability,
  and where PostgreSQL retains canonical state.
- **Model boundary:** Identify model proposals, deterministic validation, stored
  capability grants, human-only decisions, and excluded capabilities.
- **Feedback loops:** For every required human decision, identify the canonical
  decision record, the operator-facing attention item, the action that resolves
  it, the enforcement point that prevents bypass, and the rule that keeps
  ordinary informational outcomes from becoming blockers.
- **Worked examples:** For every consequential workflow decision, state change,
  human approval, blocking rule, or external effect, include a short
  plain-language example explaining what the operator sees, what they do, which
  official record changes, and what happens next.
- **Migration and retirement:** Identify existing callers and stored state, how
  each caller moves, what remains readable, and when superseded code is removed.
- **Operational checkpoint:** State the trigger, authority owner, canonical
  state, direct-or-durable rule, human-decision record, and explicit exclusions.
- **Approval:** Record user design approval before runtime or workflow changes.

The Constitution Check FAILS while any matrix row, allowed transition,
continuation rule, dependency-failure outcome, or conflict-resolution rule is
unknown. Do not defer these architecture decisions into implementation tasks.

### State and Decision Ownership Matrix

| State or decision | Business question | Canonical record and field | Authorized writer | Readers | Derived copies | Allowed transitions | Conflict resolution |
| --- | --- | --- | --- | --- | --- | --- | --- |

### Plain-Language Decision Examples

For each consequential workflow decision, approval, state transition, blocking
rule, or external effect, add a concise worked example. Do not repeat table
field names without explaining their business meaning. Each example must state:

1. what happened;
2. what the operator sees;
3. what action the operator can take, if any;
4. which official record changes; and
5. what the platform does next.
| [Name] | [What official question does this answer?] | [Exact persisted record and field] | [Single component] | [Consumers] | [Checkpoints, histories, caches, or views] | [Complete start, waiting, terminal, and failure transitions] | [Which value wins and how disagreement is repaired or surfaced] |

For workflows, also state:

- which canonical value the user interface displays;
- which canonical value authorization evaluates;
- how interrupted work resumes without treating a checkpoint as business truth;
- how retries and concurrent requests avoid duplicate or invalid transitions;
- how unavailable dependencies change official status and who records it.

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)
<!--
  ACTION REQUIRED: Replace the placeholder tree below with the concrete layout
  for this feature. Delete unused options and expand the chosen structure with
  real paths (e.g., apps/admin, packages/something). The delivered plan must
  not include Option labels.
-->

```text
# [REMOVE IF UNUSED] Option 1: Single project (DEFAULT)
src/
├── models/
├── services/
├── cli/
└── lib/

tests/
├── contract/
├── integration/
└── unit/

# [REMOVE IF UNUSED] Option 2: Web application (when "frontend" + "backend" detected)
backend/
├── src/
│   ├── models/
│   ├── services/
│   └── api/
└── tests/

frontend/
├── src/
│   ├── components/
│   ├── pages/
│   └── services/
└── tests/

# [REMOVE IF UNUSED] Option 3: Mobile + API (when "iOS/Android" detected)
api/
└── [same as backend above]

ios/ or android/
└── [platform-specific structure: feature modules, UI flows, platform tests]
```

**Structure Decision**: [Document the selected structure and reference the real
directories captured above]

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [e.g., 4th project] | [current need] | [why 3 projects insufficient] |
| [e.g., Repository pattern] | [specific problem] | [why direct DB access insufficient] |
