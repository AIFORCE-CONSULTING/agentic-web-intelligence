# Tasks: Chunk-Aware Summary Batching

**Input**: Design documents from `specs/007-chunk-aware-summary-batching/`  
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/summary-batching.md](./contracts/summary-batching.md)

**Tests**: Required. This feature changes durable summary workflow behavior and cross-service continuation rules.

**Organization**: Tasks are grouped by user story so each story can be implemented and tested independently.

## Phase 1: Setup

**Purpose**: Confirm the active feature and current implementation boundary before changing runtime code.

- [X] T001 Verify `.specify/feature.json` points to `specs/007-chunk-aware-summary-batching` and `AGENTS.md` points to `specs/007-chunk-aware-summary-batching/plan.md`
- [X] T002 Review current fixed source slicing in `apps/api/app/evidence_summaries/service.py` and current durable continuation behavior in `apps/api/app/evidence_summaries/workflow.py`
- [X] T003 [P] Review existing summary execution/work-set tests in `apps/api/tests/` and identify the files that already cover summary automation, durable workflow continuation, and report-input exclusion

---

## Phase 2: Foundational

**Purpose**: Add the shared deterministic planning surface that all user stories depend on.

**Critical**: Complete this phase before changing the user-story behavior.

- [X] T004 Create failing unit tests for deterministic chunk-aware batch planning in `apps/api/tests/test_evidence_summary_batching.py`
- [X] T005 Add a small batch-planning data structure or helper inside `apps/api/app/evidence_summaries/service.py` without changing public API routes
- [X] T006 Implement deterministic chunk-aware grouping in `apps/api/app/evidence_summaries/service.py` with 5 max sources, 15 max chunks, 1-5 chunk small sources, 6-15 chunk above-normal sources, and 16+ chunk oversized source isolation
- [X] T007 Update `apps/api/tests/test_evidence_summary_batching.py` so planner tests prove deterministic grouping, small-source grouping, above-normal source splitting, and 16+ chunk oversized-source isolation
- [X] T008 Run focused planner tests in `apps/api/tests/test_evidence_summary_batching.py`

**Checkpoint**: The summary service can plan safe work groups without changing LangGraph, Temporal, trust policy, relevance, chunking, or prompts.

---

## Phase 3: User Story 1 - Reliable Summary Progress for Mixed-Size Sources (Priority: P1)

**Goal**: Summary work is packaged by content size, so mixed small and large sources do not become one oversized Temporal execution.

**Independent Test**: Prepare source inputs with low, medium, and high chunk counts and verify the created summary executions reflect chunk-aware grouping.

### Tests for User Story 1

- [X] T009 [P] [US1] Add service-level tests proving `start_for_relevant_urls` creates multiple executions when combined chunk count would exceed 15 chunks in `apps/api/tests/test_evidence_summary_batching.py`
- [X] T010 [P] [US1] Add service-level tests proving 1-5 chunk small sources still share one execution when total chunks stay at or below 15 in `apps/api/tests/test_evidence_summary_batching.py`
- [X] T011 [P] [US1] Add service-level tests proving one 16+ chunk oversized source is isolated but not blocked in `apps/api/tests/test_evidence_summary_batching.py`
- [X] T012 [P] [US1] Add service-level tests proving planned execution groups are inspectable from existing execution/source records with source count and chunk counts in `apps/api/tests/test_evidence_summary_batching.py`

### Implementation for User Story 1

- [X] T013 [US1] Refactor `EvidenceSummaryAutomation.start_for_relevant_urls` in `apps/api/app/evidence_summaries/service.py` to prepare source chunk counts before final execution grouping
- [X] T014 [US1] Replace fixed `_MAX_SOURCES_PER_EXECUTION` slicing in `apps/api/app/evidence_summaries/service.py` with the chunk-aware planner while preserving duplicate URL removal and existing work-set reuse
- [X] T015 [US1] Ensure each planned execution is attached to the existing work set in `apps/api/app/evidence_summaries/service.py`
- [X] T016 [US1] Preserve direct-vs-durable routing through existing `EvidenceSummaryService.prepare` and `route_request` in `apps/api/app/evidence_summaries/service.py`
- [X] T017 [US1] Run the US1 batching tests in `apps/api/tests/test_evidence_summary_batching.py`

**Checkpoint**: User Story 1 is independently complete when mixed-size sources create safe execution groups and small sources still batch efficiently.

---

## Phase 4: User Story 2 - Continue Research When Some Summary Work Succeeds (Priority: P2)

**Goal**: A failed internal summary execution does not fail the whole research run when the summary work set has completed usable summaries.

**Independent Test**: Simulate a work set where one execution fails and another completes, then verify the graph continuation uses the aggregate work-set outcome.

### Tests for User Story 2

- [X] T018 [P] [US2] Add durable workflow tests for one failed execution plus one completed execution in `apps/api/tests/test_durable_execution.py`
- [X] T019 [P] [US2] Add unified workflow continuation tests proving `summarizing` advances to `assessing_coverage` when the work set completed with usable summaries in `apps/api/tests/test_unified_research_workflow.py`
- [X] T020 [P] [US2] Add failed-all-summaries tests proving the research run remains failed when no usable summaries exist in `apps/api/tests/test_unified_research_workflow.py`
- [X] T021 [P] [US2] Add failed-all-summaries tests proving the operator-facing failure code and explanation clearly say no usable summaries were available after summary processing in `apps/api/tests/test_unified_research_workflow.py`

### Implementation for User Story 2

- [X] T022 [US2] Update `EvidenceSummaryWorkflow.run` in `apps/api/app/evidence_summaries/workflow.py` so aggregate work-set status determines the graph continuation outcome
- [X] T023 [US2] Keep failed execution recording in `apps/api/app/evidence_summaries/workflow.py` without letting one failed execution overwrite a completed aggregate work-set outcome
- [X] T024 [US2] Confirm `EvidenceSummaryStore.refresh_work_set` in `apps/api/app/evidence_summaries/store.py` continues to mark a work set completed when at least one member execution completed and all members are terminal
- [X] T025 [US2] Run the US2 durable workflow and unified workflow tests in `apps/api/tests/test_durable_execution.py` and `apps/api/tests/test_unified_research_workflow.py`

**Checkpoint**: User Story 2 is independently complete when partial success continues research from completed summaries and all-failed summary work still fails safely.

---

## Phase 5: User Story 3 - Clear Operator Visibility Into Summary Work Outcomes (Priority: P3)

**Goal**: Operator-facing status distinguishes completed summaries from failed sources and keeps failed sources outside report inputs.

**Independent Test**: Complete a mixed-outcome run and verify completed summary counts, failed source details, and report-input exclusion.

### Tests for User Story 3

- [X] T026 [P] [US3] Add API/status tests for mixed completed and failed summary sources in `apps/api/tests/test_web_research.py`
- [X] T027 [P] [US3] Add coverage/report-input exclusion tests for failed summary sources in `apps/api/tests/test_agentic_research.py`
- [X] T028 [P] [US3] Add UI or response-shape regression tests for failed-source explanation text if existing coverage supports it in `apps/api/tests/test_research_report.py` or `apps/api/tests/test_web_research.py`

### Implementation for User Story 3

- [X] T029 [US3] Ensure failed summary source records include clear `failure_reason` and `failure_category` values in `apps/api/app/evidence_summaries/service.py`
- [X] T030 [US3] Ensure `AgenticResearchStore` excludes failed summary sources from coverage and report inputs in `apps/api/app/agentic_research/store.py`
- [X] T031 [US3] Update operator-facing status or summary response mapping in `apps/api/app/main.py` if mixed summary outcomes need clearer API fields
- [X] T032 [US3] Update `apps/web/src/App.tsx` only if API fields or copy must change to show completed and failed summary outcomes clearly
- [X] T033 [US3] Run US3 status, coverage, and report-input tests in `apps/api/tests/test_web_research.py`, `apps/api/tests/test_agentic_research.py`, and related report tests

**Checkpoint**: User Story 3 is independently complete when mixed summary outcomes are visible and failed sources cannot become report evidence.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Verify the full behavior, refresh documentation if behavior changed, and prepare for review.

- [X] T034 [P] Update documentation in `docs/local-evidence-intelligence.md` if operator-visible summary behavior changed
- [X] T035 [P] Update durable execution or architecture documentation in `docs/agent-runtime.md` or `docs/current-platform-architecture.md` if summary batching/continuation language changed
- [X] T036 Run full API verification: `ruff check .` and `PYTHONPATH=/workspace/apps/api pytest -q` from `apps/api`
- [X] T037 Run web build from `apps/web` if `apps/web/src/App.tsx` changed
- [X] T038 Run docs build if files under `docs/` changed
- [X] T039 Run `git diff --check`
- [X] T040 Review `specs/007-chunk-aware-summary-batching/quickstart.md` against implemented behavior and update it if verification steps changed

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 Setup**: No dependencies.
- **Phase 2 Foundational**: Depends on Phase 1.
- **Phase 3 User Story 1**: Depends on Phase 2 and provides the MVP.
- **Phase 4 User Story 2**: Depends on Phase 2; can be implemented after or alongside US1 tests, but final validation benefits from US1 batching.
- **Phase 5 User Story 3**: Depends on US1 and US2 because mixed outcomes require planned batches and continuation behavior.
- **Phase 6 Polish**: Depends on implemented stories.

### User Story Dependencies

- **US1**: First deliverable. It solves the oversized batching problem.
- **US2**: Builds on the same summary work-set boundary and fixes continuation semantics.
- **US3**: Builds on mixed execution outcomes and makes the results visible and excluded correctly.

### Parallel Opportunities

- T003 can run in parallel with setup review.
- T009, T010, and T011 can be written in parallel because they are separate planner scenarios.
- T017, T018, and T019 can be written in parallel because they target different workflow outcomes.
- T024, T025, and T026 can be written in parallel because they target status, coverage, and UI/API visibility.
- Documentation tasks T034 and T035 can run in parallel after behavior is stable.

---

## Parallel Example: User Story 1

```text
Task: "Add service-level tests proving start_for_relevant_urls creates multiple executions when combined chunk count would exceed 15 chunks in apps/api/tests/test_evidence_summary_batching.py"
Task: "Add service-level tests proving small sources still share one execution when total chunks stay at or below 15 in apps/api/tests/test_evidence_summary_batching.py"
Task: "Add service-level tests proving one oversized source is isolated in apps/api/tests/test_evidence_summary_batching.py"
```

---

## Implementation Strategy

### MVP First

1. Complete Phase 1 and Phase 2.
2. Implement Phase 3 only.
3. Validate that chunk-aware grouping prevents oversized work groups while preserving efficient small-source batching.
4. Stop for review if the batching behavior differs from the plan.

### Incremental Delivery

1. Deliver US1: safer work grouping.
2. Deliver US2: aggregate continuation semantics.
3. Deliver US3: operator visibility and report-input exclusion.
4. Finish cross-cutting verification and documentation.

### Notes

- Tests should be written before implementation for each story.
- Do not change chunk size, prompts, discovery, trust, relevance, or report grading in this feature.
- Do not add a new table unless implementation proves the existing execution/source records cannot satisfy the contract; if that happens, stop for design review.
- Commit after each coherent slice or when the user asks.
