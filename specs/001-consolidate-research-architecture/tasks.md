# Tasks: Consolidated Research Architecture

**Input**: Design documents from `specs/001-consolidate-research-architecture/`  
**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`

**Tests**: Authority, workflow, MCP, durable execution, human review, migration,
and cross-service behavior require tests before their implementation tasks.

**Organization**: Tasks are grouped by user story. Because explicit authority
is a prerequisite for the operator workflow, User Story 2 is implemented before
User Story 1 even though both are Priority P1.

**Architecture readiness**: T001–T004 record approval and the resolved C1, C2,
and C3 designs. The plan's Constitution Check passes; runtime work may proceed
in the dependency order below.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can proceed in parallel in different files after its prerequisites
- **[Story]**: Maps to the numbered user story in `spec.md`
- Every task identifies the exact file or directory it changes

## Phase 1: Setup and Design Approval

**Purpose**: Close requirement gaps and receive the required architecture gate
before changing runtime or workflow code.

- [x] T001 Record explicit user approval of the architecture reconciliation and operational checkpoint in `specs/001-consolidate-research-architecture/plan.md`
- [x] T002 Define the canonical research-status owner, complete transition table, UI and RuntimeService readers, checkpoint and Temporal boundaries, optimistic concurrency, retry rules, and success, duplicate-completion, stale-checkpoint, wrong-workspace, failed-work, and restart outcomes in `specs/001-consolidate-research-architecture/spec.md`, `plan.md`, `data-model.md`, and `contracts/workflow-continuation.md`
- [x] T003 Define official checkpointer setup, strict serialization, `unified-research:v1` namespace versioning, resumable retention, terminal and research-deletion cleanup, idempotent cleanup retry, and one-time obsolete-checkpoint reset in `specs/001-consolidate-research-architecture/plan.md` and `data-model.md`
- [x] T004 Assign PostgreSQL, checkpointer, Temporal, MCP search, MCP extraction, and local-model unavailability to typed owners, official outcomes, safe operator responses, no-fallback rules, and recovery paths in `specs/001-consolidate-research-architecture/spec.md`, `plan.md`, `data-model.md`, and `contracts/`
- [x] T005 Add the official LangGraph PostgreSQL checkpointer and required PostgreSQL driver packages to `apps/api/pyproject.toml`, `apps/api/requirements.lock`, and `apps/api/requirements-dev.lock` using `scripts/update-python-locks.ps1`

**Checkpoint**: Architecture approved, requirement gaps closed, dependencies pinned.

---

## Phase 2: Foundational Contracts and Persistence

**Purpose**: Establish shared authority and resumable-workflow foundations that
block every user story.

**Critical**: No production caller migration begins until this phase passes.

- [x] T006 [P] Define authority-policy version, stable decision reason codes, capability request, authorization decision, and MCP execution-correlation contracts in `apps/api/app/agent_runtime/contracts.py`
- [x] T007 [P] Define versioned workflow thread, durable wait, and continuation-envelope contracts in `apps/api/app/durable_execution/contracts.py`
- [x] T008 Add `status_version`, `failed_stage`, `workflow_version`, `failure_code`, safe `failure_explanation`, `retryable`, `failed_at`, and append-only transition audits to ResearchStore; add the research-task link and authority-policy version to runtime records; and extend MCP execution audits with research, runtime, step, authorization-decision, request, tool, bounded-resource, outcome, and time correlation in `apps/api/app/web_research/store.py`, `apps/api/app/web_research/contracts.py`, `apps/api/app/agent_runtime/store.py`, and `apps/api/app/agent_runtime/contracts.py`
- [x] T009 Move query reservation, source-attempt, gap-round, and capability-decision persistence under `RuntimeStore` in `apps/api/app/agent_runtime/store.py`, retaining transactional uniqueness and limits
T010 is dependency-ordered after T020–T022 in Phase 3 so the active caller is
migrated before duplicate persistence is removed.
- [x] T011 Create the official async PostgreSQL checkpointer lifecycle adapter inside `apps/api/app/agent_runtime/research_workflow.py` using the existing database configuration, strict MessagePack handling, `unified-research:v1`, research-task UUID thread IDs, startup `setup()`, post-terminal/research-deletion `adelete_thread()`, cleanup auditing, oldest-100 startup retry, degraded-readiness backlog reporting, and the bounded maintenance command
- [x] T012 [P] Add schema and store tests for the complete research-status transition table, expected-version conflicts, idempotent transition identities, typed dependency-failure fields, failed-stage retries, research-task assignment uniqueness, policy versions, reservations, counters, allow/deny records, and complete MCP execution-audit correlation in `apps/api/tests/test_web_research.py` and `apps/api/tests/test_agent_runtime.py`
- [x] T013 [P] Add checkpointer setup failure, strict serialization, namespace, active/waiting/failed retention, completed/deleted thread cleanup, idempotent cleanup retry, restart, and incompatible-namespace contract tests in `apps/api/tests/test_unified_research_workflow.py`
- [x] T014 Document the stopped-process selective local clean-start procedure for obsolete runtime/control records, paged checkpoint enumeration and official thread deletion followed by `setup()`, and obsolete Temporal histories in `specs/001-consolidate-research-architecture/quickstart.md`

**Checkpoint**: Shared stored authority and framework checkpointing are ready.

---

## Phase 3: User Story 2 - Explicit and Explainable Agent Authority (Priority: P1)

**Goal**: Every model-proposed web action is authorized from stored platform
facts and recorded before governed MCP execution.

**Independent Test**: Submit the full authorization matrix and demonstrate that
only explicitly granted, active, in-scope requests are allowed and every other
combination receives a stored denial reason.

### Tests for User Story 2

- [ ] T015 [P] [US2] Replace object-based capability tests with stored-request authorization tests in `apps/api/tests/test_agent_runtime.py`
- [ ] T016 [P] [US2] Add the complete role/action/research-status/workspace/task/source/limit default-deny matrix and prove RuntimeService reads but cannot write `research_runs.status` in `apps/api/tests/test_research_controls.py`
- [ ] T017 [P] [US2] Add contract tests proving decisions exclude secrets and raw evidence, are stored before tool invocation, and require matching workspace, research, runtime, step, decision, request, tool, and resource identities in the MCP audit in `apps/api/tests/test_research_capabilities.py`
- [ ] T018 [P] [US2] Add race tests for state changes between authorization and execution and transactional limit exhaustion in `apps/api/tests/test_research_controls.py`

### Implementation for User Story 2

- [ ] T019 [US2] Add the versioned authority rules, permitted stages, and stable reason-code mapping in `apps/api/app/agent_runtime/policy.py`
- [ ] T020 [US2] Extend `RuntimeService` to create or reuse one stored research assignment and server-owned researcher step in `apps/api/app/agent_runtime/service.py`
- [ ] T021 [US2] Replace `authorize_capability(RuntimeStep, capability)` with canonical-record authorization and persisted decisions in `apps/api/app/agent_runtime/service.py`
- [ ] T022 [US2] Integrate query reservation, discovered-source scope, source/attempt/retry limits, and two-round gap limits into `RuntimeService` in `apps/api/app/agent_runtime/service.py`
- [ ] T010 [US2] Remove the migrated authority/control persistence methods from `AgenticResearchStore`, retaining only topics, relevance, coverage, discovered-source associations, and reports in `apps/api/app/agentic_research/store.py`
- [ ] T023 [US2] Refactor the model-visible capability catalog to provide schemas only and remove caller-supplied grant authority in `apps/api/app/agentic_research/capabilities.py`
- [ ] T024 [US2] Add an in-process typed invocation method that preserves the existing registry, validation, provider selection, and normalization; verifies the stored allow decision correlation before provider invocation; and writes the fully correlated MCP execution audit in `apps/api/app/web_research/mcp_host.py`
- [ ] T025 [US2] Update runtime and capability audit reads to expose safe policy version, reason code, and explanation fields in `apps/api/app/agent_runtime/store.py` and `apps/api/app/main.py`; do not extend the retiring runtime-run API for durable-work compatibility

**Checkpoint**: RuntimeService is the one tested authorization boundary.

---

## Phase 4: User Story 1 - Start One Governed Research Workflow (Priority: P1)

**Goal**: The existing **Discover Sources** action starts or resumes one
checkpointed LangGraph that uses established services and deterministic
direct-versus-Temporal routing.

**Independent Test**: Start research from the existing API/UI contract and
observe one research task progress through planning, discovery, acquisition,
relevance, summaries, coverage, bounded gap searches, and reporting without a
parallel run.

### Tests for User Story 1

- [ ] T026 [P] [US1] Add failing API contract tests for thin `POST /v1/research/runs` start/reuse behavior, unchanged 200/201 responses, service-unavailable responses for PostgreSQL/checkpointer/Temporal readiness, safe failed-run details, and the replacement workspace-scoped `/v1/research/durable-work` list/detail contract in `apps/api/tests/test_web_research.py`
- [ ] T027 [P] [US1] Replace harness-supplied grants with RuntimeService and governed MCP test doubles, asserting every agent tool call links to exactly one matching prior allow decision and mismatches fail before provider invocation, in `apps/api/tests/test_unified_research_integration.py`
- [ ] T028 [P] [US1] Add complete graph status-transition, checkpoint, interrupt, resume, duplicate-start, stale-checkpoint, optimistic-concurrency conflict, and canonical-state reconstruction tests in `apps/api/tests/test_unified_research_workflow.py`
- [ ] T029 [P] [US1] Add direct and Temporal-backed end-to-end cases for source limits, known-URL reuse, idempotent retries, two gap rounds, grounded reports, PostgreSQL loss without replacement state, dependency recovery from the stored failed stage, and durable-work visibility that agrees with each owning store in `apps/api/tests/test_unified_research_integration.py`
- [ ] T030 [P] [US1] Add deterministic Temporal workflow tests for successful continuation, mandatory readiness, unavailable scheduling without direct fallback, exhausted retries, duplicate and late continuation, stale wait, status-version mismatch, wrong workspace, failed work, and worker restart, proving Temporal never writes research status, in `apps/api/tests/test_durable_execution.py`

### Implementation for User Story 1

- [ ] T031 [US1] Refactor search and missing-topic nodes to request RuntimeService authorization, invoke `web.search` through the governed MCP boundary, and distinguish typed provider unavailability from an empty result before recording `search_unavailable` in `apps/api/app/agentic_research/workflow_nodes.py`
- [ ] T032 [US1] Refactor acquisition nodes and `CandidatePreflightService` to execute authorized `web.extract` through the governed MCP boundary, distinguish provider unavailability from a source-level unreachable outcome, and record `extraction_unavailable` without duplicating trust policy in `apps/api/app/agentic_research/workflow_nodes.py` and `apps/api/app/web_trust/preflight.py`
- [ ] T033 [US1] Compile the canonical graph with the PostgreSQL checkpointer, implement the approved guarded research-status transitions through ResearchStore, and replace placeholder waits with standard LangGraph interrupts/resume commands in `apps/api/app/agent_runtime/research_workflow.py`
- [ ] T034 [US1] Add a bounded graph start/resume adapter that creates or reuses the research record, treats `research_runs.status` as authoritative, and reconstructs business facts through existing services rather than checkpoint data in `apps/api/app/agent_runtime/research_workflow.py`
- [ ] T035 [US1] Extend preflight and summary Temporal inputs with typed thread and expected-resume metadata in `apps/api/app/web_trust/workflow.py`, `apps/api/app/evidence_summaries/workflow.py`, and `apps/api/app/durable_execution/contracts.py`
- [ ] T036 [US1] Add idempotent LangGraph continuation activities after persisted preflight and summary outcomes, comparing expected research status and version while leaving status writes to the resumed graph, in `apps/api/app/durable_execution/worker.py`
- [ ] T037 [US1] Update `CandidatePreflightWorkflow` and `EvidenceSummaryWorkflow` to schedule their existing work activity followed by the typed continuation activity in `apps/api/app/web_trust/workflow.py` and `apps/api/app/evidence_summaries/workflow.py`
- [ ] T038 [US1] Wire RuntimeService, the compiled graph, checkpointer lifecycle, mandatory PostgreSQL/checkpointer/Temporal readiness, MCP invocation, and continuation dependencies into application startup/shutdown without fallback substitution in `apps/api/app/main.py`
- [ ] T039 [US1] Refactor `POST /v1/research/runs` into the thin authenticated start/resume route defined by `contracts/research-api.md`, delegating record creation and every status transition to the unified graph adapter, and add the replacement read-only research durable-work list/detail endpoints defined by `contracts/durable-work-api.md` in `apps/api/app/main.py`
- [ ] T040 [US1] Preserve existing Research UI submission and source-count choices, make polling display `research_runs.status` exclusively, show safe dependency failure, failed stage, and retryability details, and reconnect the Admin Durable work section to the replacement research durable-work endpoint with no retired-workflow controls in `apps/web/src/App.tsx`

**Checkpoint**: The existing operator action runs the unified governed workflow.

---

## Phase 5: User Story 3 - Preserve Evidence Trust and Human Review (Priority: P1)

**Goal**: Only trust-eligible, topic-relevant evidence reaches model context,
and human acceptance remains independently recorded and enforced.

**Independent Test**: Process eligible, blocked, review-required, accepted,
expired, irrelevant, and malformed evidence and prove only eligible/relevant or
exactly accepted evidence can reach summaries, coverage, and reporting.

### Tests for User Story 3

- [ ] T041 [P] [US3] Add graph integration cases for eligible, blocked, review-required, expired-acceptance, irrelevant, malformed planning and relevance output, and local-model unavailability at planning, relevance, summary, coverage, and reporting stages in `apps/api/tests/test_unified_research_integration.py`
- [ ] T042 [P] [US3] Add exact evidence-version human acceptance and repeated/expired decision tests in `apps/api/tests/test_web_trust.py`
- [ ] T043 [P] [US3] Add final-report source-grounding tests proving excluded evidence never enters model input in `apps/api/tests/test_research_workflow_nodes.py`

### Implementation for User Story 3

- [ ] T044 [US3] Ensure relevance, summary, coverage, and reporting nodes reload and enforce stored trust and exact human-review facts through existing owners in `apps/api/app/agentic_research/workflow_nodes.py`
- [ ] T045 [US3] Add the human-review LangGraph interrupt and bounded resume path without moving acceptance authority out of `EvidenceTrustService` in `apps/api/app/agent_runtime/research_workflow.py`
- [ ] T046 [US3] Resume a waiting graph only after the existing acceptance route stores and reloads a matching evidence-version decision in `apps/api/app/main.py`
- [ ] T047 [US3] Preserve trust decision and acceptance audit attribution while adding workflow-resume metadata in `apps/api/app/web_trust/service.py` and `apps/api/app/web_trust/store.py`

**Checkpoint**: Trust and human review remain independent of orchestration.

---

## Phase 6: User Story 4 - Retire Duplicate Paths Cleanly (Priority: P2)

**Goal**: Remove overlapping workflow and authority paths after all production
callers, required tests, and operational visibility use the consolidated path.

**Independent Test**: A repository-wide caller audit finds no active route,
startup wiring, service, worker, or workflow registration for retired paths,
while retained data remains usable and the documented clean start succeeds.

### Tests for User Story 4

- [ ] T048 [P] [US4] Transfer useful plain-Python router transition cases into canonical graph tests in `apps/api/tests/test_unified_research_workflow.py`
- [ ] T049 [P] [US4] Transfer old first-result graph and reviewer safety cases into RuntimeService and unified integration tests in `apps/api/tests/test_agent_runtime.py` and `apps/api/tests/test_unified_research_integration.py`
- [ ] T050 [P] [US4] Add a source-level retirement guard that fails when production code imports retired classes, registers `GovernedRuntimeWorkflow`, retains the old `/v1/runtime/runs` workflow controls, or exposes approval/cancellation controls in the consolidated Durable work section in `apps/api/tests/test_unified_research_integration.py` and `apps/web/src/App.test.tsx`

### Implementation for User Story 4

- [ ] T051 [US4] Remove `AgenticResearchControlService` and migrate remaining imports/tests from `apps/api/app/agentic_research/control.py`
- [ ] T052 [US4] Remove `ResearchOrchestrationService` after routing coverage is present in the canonical graph and delete `apps/api/app/agentic_research/orchestration.py`
- [ ] T053 [US4] Remove obsolete deterministic planning, first-result execution, reviewer-cycle, and scheduling functions from `apps/api/app/agent_runtime/workflow.py`
- [ ] T054 [US4] Remove `GovernedRuntimeWorkflow`, its scheduling boundary, worker registration, obsolete tests, application startup dependencies, and the old `/v1/runtime/runs` list, detail, approval, attention, and durable-cancellation routes from `apps/api/app/durable_execution/workflows.py`, `apps/api/app/durable_execution/service.py`, `apps/api/app/durable_execution/worker.py`, `apps/api/app/main.py`, `apps/api/tests/test_durable_execution.py`, and superseded runtime-route tests after the replacement research durable-work endpoints and UI are verified
- [ ] T055 [US4] Apply and document the selected clean start, deleting obsolete RuntimeService workflow and durable test records while preserving only useful evidence-domain fixtures, in `specs/001-consolidate-research-architecture/quickstart.md` and the existing store schema setup paths
- [ ] T056 [US4] Run the repository-wide caller audit and record retired and retained components in `specs/001-consolidate-research-architecture/retirement-report.md`

**Checkpoint**: No duplicate authority or orchestration path remains active.

---

## Phase 7: User Story 5 - Understand the Running Architecture (Priority: P3)

**Goal**: Architecture records describe the exact path exercised by end-to-end
tests and make one owner visible for every governed responsibility.

**Independent Test**: Trace the running path from Discover Sources to stored
report using the diagram, glossary, ADR, and runtime documentation without
encountering a contradictory owner or retired active path.

### Documentation for User Story 5

- [ ] T057 [P] [US5] Amend ADR 0016 with the consolidated RuntimeService, LangGraph, MCP, PostgreSQL-checkpoint, and Temporal-continuation decisions in `docs/adr/0016-governed-local-agent-capability-requests.md`
- [ ] T058 [P] [US5] Replace the current-state architecture record with the tested target path and clearly identify checkpoint versus business state in `docs/current-platform-architecture.md`
- [ ] T059 [P] [US5] Update every affected entity's purpose, inputs, outputs, and connections in `docs/architecture-glossary.md`
- [ ] T060 [P] [US5] Update runtime, durable-execution, local-evidence, and MCP documentation under `docs/` to match the consolidated callers and ownership boundaries
- [ ] T061 [US5] Update Phase 7.5 completion boxes and retirement notes only after implementation and tests agree in `./ROADMAP.md`

**Checkpoint**: Documentation and running architecture agree.

---

## Phase 8: Final Verification and Cross-Cutting Quality

**Purpose**: Prove the complete feature and close its requirements checklist.

- [ ] T062 Run Ruff and the complete API test suite in the pinned Python 3.12 environment defined by `apps/api/requirements-dev.lock`
- [ ] T063 [P] Run the TypeScript and Vite production build defined by `apps/web/package.json`
- [ ] T064 [P] Run the strict MkDocs build defined by `docs/requirements.lock`
- [ ] T065 Execute the operator and restart scenarios in `specs/001-consolidate-research-architecture/quickstart.md` against the local Compose platform
- [x] T066 Review and resolve every item in `specs/001-consolidate-research-architecture/checklists/architecture.md`, updating source requirements for any failed item
- [x] T067 Run `/speckit.analyze` against `spec.md`, `plan.md`, and `tasks.md` and resolve all critical or high-severity inconsistencies

---

## Dependencies and Execution Order

### Phase dependencies

- **Phase 1** has no implementation dependency and contains the mandatory user
  architecture approval.
- **Phase 2** depends on Phase 1 and blocks every user story.
- **User Story 2 / Phase 3** establishes authority and blocks User Story 1.
- **User Story 1 / Phase 4** establishes the active workflow and blocks trust
  resume, retirement, and final documentation.
- **User Story 3 / Phase 5** depends on User Stories 2 and 1.
- **User Story 4 / Phase 6** depends on User Stories 2, 1, and 3 because old
  paths cannot be removed before callers and safety behavior migrate.
- **User Story 5 / Phase 7** depends on the tested implementation and retirement.
- **Final Verification / Phase 8** depends on all selected user stories.

### User story dependency graph

```text
Setup and design approval
        ↓
Foundational contracts and persistence
        ↓
US2 Explicit authority
        ↓
US1 One governed workflow
        ↓
US3 Trust and human review
        ↓
US4 Clean retirement
        ↓
US5 Accurate architecture records
        ↓
Final verification
```

### Parallel opportunities

- T006 and T007 can proceed in parallel after approval.
- T012 and T013 can proceed in parallel after foundational schemas exist.
- US2 test tasks T015–T018 can be written in parallel before implementation.
- US1 test tasks T026–T030 can be written in parallel after authority contracts
  stabilize.
- US3 test tasks T041–T043 can be written in parallel.
- US4 migration-test tasks T048–T050 can be written in parallel.
- US5 documentation tasks T057–T060 can proceed in parallel after the running
  architecture is stable.
- Web and documentation builds T063–T064 can run in parallel with API lint/tests.

## Parallel Example: User Story 1

```text
T026: API start/reuse contract tests in test_web_research.py
T027: RuntimeService + MCP integration harness in test_unified_research_integration.py
T028: Checkpoint and interrupt tests in test_unified_research_workflow.py
T029: End-to-end limits and report tests in test_unified_research_integration.py
T030: Temporal continuation tests in test_durable_execution.py
```

After these failing tests establish the contract, implement T031–T040 in order
where files or dependencies overlap.

## Implementation Strategy

### First deliverable: authority foundation

1. Complete Phases 1 and 2.
2. Complete User Story 2 so one stored authorization boundary exists.
3. Stop and review the decision matrix and audit records before changing the
   production route.

### MVP: one governed operator workflow

1. Complete User Story 1 after authority passes.
2. Demonstrate the existing Discover action on direct and Temporal-backed work.
3. Keep old paths present but inactive until trust/review and caller migration
   tests pass.

### Safe consolidation

1. Complete User Story 3 to preserve trust and human decisions.
2. Complete User Story 4 to retire duplicate code only after zero callers.
3. Complete User Story 5 and final verification to align all records.

## Notes

- Tests are written before the implementation they govern and must initially
  fail for the expected missing behavior.
- Tasks marked `[P]` touch separate files or establish independent tests.
- Commit after each coherent task group, not necessarily every single task.
- Do not add a new service, store, workflow engine, policy authority, MCP host,
  or worker when an existing canonical owner can be extended.
- Stop at each checkpoint for review; never retire an old path before callers,
  tests, and operational visibility have moved.
