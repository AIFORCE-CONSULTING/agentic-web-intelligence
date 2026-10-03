# Tasks: Completed Checkpoint Cleanup

**Input**: Design documents from `/specs/005-checkpoint-cleanup/`  
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Required. This feature touches workflow readiness, checkpoint
maintenance, and persisted audit behavior, so contract and integration coverage
must be added before implementation.

**Organization**: Tasks are grouped by user story to enable independent
implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to
- Include exact file paths in descriptions

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm the active feature context and current owner boundaries.

- [X] T001 Confirm `.specify/feature.json` points to `specs/005-checkpoint-cleanup` and the current Git branch is `005-checkpoint-cleanup`
- [X] T002 [P] Review existing checkpoint lifecycle tests in `apps/api/tests/test_unified_research_workflow.py`
- [X] T003 [P] Review existing research start/readiness tests in `apps/api/tests/test_web_research.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Preserve the approved architecture before story work begins.

**Critical**: No user story work should begin until this phase is complete.

- [X] T004 Reconcile existing cleanup ownership in `apps/api/app/agent_runtime/research_workflow.py` and `apps/api/app/web_research/store.py` against `specs/005-checkpoint-cleanup/plan.md`
- [X] T005 Verify the State and Decision Ownership Matrix in `specs/005-checkpoint-cleanup/plan.md` still names one canonical record, one writer, all readers, derived copies, transitions, and conflict resolution for checkpoint cleanup
- [X] T006 Confirm no new cleanup service, store, workflow, Temporal workflow, MCP tool, or model-owned action is needed in `specs/005-checkpoint-cleanup/plan.md` before editing runtime code

**Checkpoint**: Foundation ready. User story implementation can start.

---

## Phase 3: User Story 1 - Start New Research After Completion (Priority: P1) MVP

**Goal**: A completed-run checkpoint cleanup backlog must not block a different
new research request.

**Independent Test**: Complete or simulate a completed research run with
pending cleanup, then start a different research question. The new research run
is accepted without manual cleanup.

### Tests for User Story 1

- [X] T007 [P] [US1] Add a failing workflow test proving `ResearchCheckpointLifecycle.readiness` reports cleanup backlog as degraded maintenance while remaining start-eligible in `apps/api/tests/test_unified_research_workflow.py`
- [X] T008 [P] [US1] Add a failing API contract test proving pending completed-run cleanup does not return the blocking "Completed research checkpoint cleanup is pending." response for a new unrelated research request in `apps/api/tests/test_web_research.py`

### Implementation for User Story 1

- [X] T009 [US1] Extend `CheckpointReadiness` in `apps/api/app/agent_runtime/research_workflow.py` so it reports checkpoint infrastructure availability separately from completed-run cleanup maintenance backlog; backlog may set a maintenance/degraded detail but must not set the research-start blocker flag by itself
- [X] T010 [US1] Update `ResearchCheckpointLifecycle.readiness` in `apps/api/app/agent_runtime/research_workflow.py` so completed-run cleanup backlog no longer makes unrelated research starts unavailable
- [X] T011 [US1] Update `UnifiedResearchWorkflowEntry.start_or_resume` in `apps/api/app/agent_runtime/research_workflow.py` to block only on checkpoint infrastructure unavailability, not completed-run cleanup maintenance backlog
- [X] T012 [US1] Update health/readiness response handling in `apps/api/app/main.py` so cleanup backlog appears as degraded maintenance detail instead of a hard blocker, using operator-visible wording that explains cleanup affects execution bookmarks only and does not delete completed research outputs

**Checkpoint**: User Story 1 should allow a new unrelated research run when
only completed-run cleanup backlog exists.

---

## Phase 4: User Story 2 - Preserve Completed Research Results (Priority: P2)

**Goal**: Cleanup removes only completed-run execution bookmarks and never
alters completed research outputs.

**Independent Test**: Complete or simulate a research run with stored outputs,
run cleanup, and verify outputs remain readable while checkpoint cleanup is
audited.

### Tests for User Story 2

- [X] T013 [US2] Add a failing workflow test proving cleanup is triggered only after the graph returns, the stored research run is reloaded or confirmed as `completed`, and a succeeded audit is recorded without changing completed research status in `apps/api/tests/test_unified_research_workflow.py`
- [X] T013A [US2] Add a failing workflow/store test proving representative completed research outputs remain readable after cleanup, including source summaries, keywords, final report records, trust/evaluation records, and audit history in `apps/api/tests/test_unified_research_workflow.py`
- [X] T014 [US2] Add a failing workflow test proving cleanup targets only completed runs and skips active, waiting, failed, and review-required runs in `apps/api/tests/test_unified_research_workflow.py`

### Implementation for User Story 2

- [X] T015 [US2] Extend `UnifiedResearchWorkflowEntry.start_or_resume` in `apps/api/app/agent_runtime/research_workflow.py` to invoke best-effort completed-run cleanup only after the graph invocation has returned and the persisted research run has been reloaded or confirmed as `completed`
- [X] T016 [US2] Ensure `ResearchCheckpointLifecycle.delete_thread` in `apps/api/app/agent_runtime/research_workflow.py` records cleanup audit outcomes without modifying `research_runs.status`
- [X] T017 [US2] Update cleanup candidate handling in `apps/api/app/web_research/store.py` if needed so only completed runs without a successful cleanup audit are returned
- [X] T018 [US2] Verify cleanup uses the existing saver deletion path and does not introduce direct SQL deletion in `apps/api/app/agent_runtime/research_workflow.py`

**Checkpoint**: User Story 2 should clean completed-run bookmarks while
preserving research outputs and audit history.

---

## Phase 5: User Story 3 - Recover From Cleanup Failure (Priority: P3)

**Goal**: Cleanup failure is visible, retryable, and does not corrupt completed
research state or block unrelated new research.

**Independent Test**: Simulate cleanup failure, verify the run stays completed,
the failure is audited, a different research run can start, and bounded retry
can later succeed.

### Tests for User Story 3

- [X] T019 [US3] Add a failing workflow test proving cleanup failure records a failed audit, leaves the run completed, and does not raise through research completion in `apps/api/tests/test_unified_research_workflow.py`
- [X] T020 [US3] Add a failing retry test proving `retry_completed_cleanup` can convert a prior failed cleanup backlog to succeeded after the saver becomes available in `apps/api/tests/test_unified_research_workflow.py`
- [X] T021 [P] [US3] Add a failing API test proving a failed cleanup backlog does not block a new unrelated research run in `apps/api/tests/test_web_research.py`

### Implementation for User Story 3

- [X] T022 [US3] Update `ResearchCheckpointLifecycle.delete_thread` in `apps/api/app/agent_runtime/research_workflow.py` so cleanup failures are swallowed after failed audit recording and never reverse completion
- [X] T023 [US3] Update `ResearchCheckpointLifecycle.retry_completed_cleanup` in `apps/api/app/agent_runtime/research_workflow.py` to keep bounded retry behavior and return remaining maintenance backlog
- [X] T024 [US3] Ensure `ResearchStore.checkpoint_cleanup_backlog` in `apps/api/app/web_research/store.py` treats any successful cleanup audit as terminal for backlog purposes
- [X] T025 [US3] Ensure failed cleanup explanations are safe and operator-readable in `apps/api/app/agent_runtime/research_workflow.py`

**Checkpoint**: User Story 3 should keep cleanup failure recoverable and
non-disruptive.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, verification, and cleanup after all user stories.

- [X] T026 [P] Update checkpoint cleanup documentation in `docs/agent-runtime.md`
- [X] T027 [P] Update architecture notes for checkpoint cleanup health behavior in `docs/current-platform-architecture.md`
- [X] T028 [P] Update or add quickstart verification notes in `specs/005-checkpoint-cleanup/quickstart.md`
- [X] T029 Run focused workflow tests for checkpoint cleanup in `apps/api/tests/test_unified_research_workflow.py`
- [X] T030 Run API research readiness tests in `apps/api/tests/test_web_research.py`
- [X] T031 Run full API lint and test verification from `apps/api`
- [X] T032 Run `git diff --check` from `C:\Users\jonca\Documents\ChatGPT\ENTERPRISE PLATFORM TUTORIAL`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup; blocks story implementation.
- **User Story 1 (Phase 3)**: Depends on Foundational and is the MVP.
- **User Story 2 (Phase 4)**: Can start after Foundational, but should land after US1 so research start behavior is already corrected.
- **User Story 3 (Phase 5)**: Can start after Foundational, but should land after US2 so failure behavior wraps the completed cleanup path.
- **Polish (Phase 6)**: Depends on selected user stories.

### User Story Dependencies

- **US1**: No dependency on other stories after Foundational.
- **US2**: Builds on the completed-run cleanup path verified in US1.
- **US3**: Builds on the cleanup path from US2 and hardens failure/retry.

### Within Each User Story

- Write failing tests first.
- Implement the smallest code change that makes those tests pass.
- Verify the story independently before moving to the next priority.

---

## Parallel Execution Examples

### User Story 1

```text
Task: T007 workflow readiness test in apps/api/tests/test_unified_research_workflow.py
Task: T008 API blocking-message regression test in apps/api/tests/test_web_research.py
```

### User Story 2

```text
Task: T013 post-completion cleanup audit test in apps/api/tests/test_unified_research_workflow.py
Task: T013A completed-output preservation test in apps/api/tests/test_unified_research_workflow.py
Task: T014 completed-only cleanup eligibility test in apps/api/tests/test_unified_research_workflow.py
```

### User Story 3

```text
Task: T019 cleanup failure audit test in apps/api/tests/test_unified_research_workflow.py
Task: T020 bounded retry success test in apps/api/tests/test_unified_research_workflow.py
Task: T021 failed-backlog API start test in apps/api/tests/test_web_research.py
```

---

## Implementation Strategy

### MVP First

1. Complete Setup and Foundational tasks.
2. Complete US1 so cleanup backlog no longer blocks new unrelated research.
3. Stop and verify with focused workflow/API tests.

### Incremental Delivery

1. US1 removes the disruptive operator blocker.
2. US2 ensures successful cleanup happens automatically and safely after completion.
3. US3 hardens failure and retry behavior.
4. Polish updates documentation and runs full verification.

### Notes

- Cleanup is maintenance. It must never become official research status.
- Use the existing checkpointer deletion abstraction; do not write direct SQL
  against framework checkpoint tables.
- Do not introduce a model, MCP, Temporal, or new workflow decision path.
- Commit after each coherent slice or at story checkpoints.
