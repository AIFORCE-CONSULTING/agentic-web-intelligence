# Tasks: Correct Report Exclusion Labels

**Input**: Design documents from `/specs/008-fix-exclusion-labels/`  
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Required. This feature corrects a user-visible report classification
bug and must prove every exclusion category is derived from stored platform
outcomes rather than model output or UI inference.

**Organization**: Tasks are grouped by user story to enable independent
implementation and testing.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm the active feature and current reporting owner before
implementation.

- [X] T001 Verify `.specify/feature.json` points to `specs/008-fix-exclusion-labels` and `AGENTS.md` references `specs/008-fix-exclusion-labels/plan.md`
- [X] T002 Review the current exclusion derivation in `apps/api/app/agentic_research/store.py` and identify existing reason-code branches before editing
- [X] T003 [P] Review the current report contract type in `apps/api/app/agentic_research/contracts.py` and confirm whether allowed reason codes need type documentation only

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Establish shared reason-code expectations before user-story
implementation.

**CRITICAL**: No user story work should begin until this phase is complete.

- [X] T004 Define the canonical report exclusion reason code constants or helper mapping in `apps/api/app/agentic_research/store.py`
- [X] T005 [P] Add focused test fixtures for report exclusion source outcomes in `apps/api/tests/test_agentic_research.py`
- [X] T006 [P] Inspect `apps/api/app/agentic_research/contracts.py`; add explicit report-exclusion reason-code type documentation there, or record in implementation notes that the existing free-form contract intentionally remains unchanged

**Checkpoint**: Foundation ready - user story implementation can now begin.

---

## Phase 3: User Story 1 - Understand Why a Source Was Not Used (Priority: P1)

**Goal**: Blocked extraction and publisher access denial are not mislabeled as
topic irrelevance.

**Independent Test**: A stored report exclusion for an HTTP 403 or otherwise
publisher-denied source returns `access_denied_by_publisher`, while a true
topic relevance miss returns `not_relevant_to_planned_topics`.

### Tests for User Story 1

- [X] T007 [P] [US1] Add failing test for publisher access denial producing `access_denied_by_publisher` in `apps/api/tests/test_agentic_research.py`
- [X] T008 [P] [US1] Add failing test for local trust block producing `blocked_by_trust_policy` in `apps/api/tests/test_agentic_research.py`
- [X] T009 [P] [US1] Add failing test proving `not_relevant_to_planned_topics` is used only after usable summarized evidence exists in `apps/api/tests/test_agentic_research.py`

### Implementation for User Story 1

- [X] T010 [US1] Update `AgenticResearchStore.report_exclusions` in `apps/api/app/agentic_research/store.py` to classify local trust blocks as `blocked_by_trust_policy`
- [X] T011 [US1] Update `AgenticResearchStore.report_exclusions` in `apps/api/app/agentic_research/store.py` to classify publisher access denial such as HTTP 403 as `access_denied_by_publisher`
- [X] T012 [US1] Update `AgenticResearchStore.report_exclusions` in `apps/api/app/agentic_research/store.py` so topic-irrelevance wording is used only after usable summary outcomes are present
- [X] T013 [US1] Run the focused US1 tests in `apps/api/tests/test_agentic_research.py`

**Checkpoint**: User Story 1 should independently fix the misleading
not-relevant label for extraction-blocked sources.

---

## Phase 4: User Story 2 - Troubleshoot Report Gaps (Priority: P2)

**Goal**: Operators can distinguish all report exclusion categories without
reading logs.

**Independent Test**: A report with mixed exclusion causes returns distinct
plain-language reasons for blocked policy, publisher denial, unreachable,
summary failed, evidence insufficient, and not relevant to planned topics.

### Tests for User Story 2

- [X] T014 [P] [US2] Add failing test for timeout, empty extraction, or missing-detail acquisition failure producing `unreachable` in `apps/api/tests/test_agentic_research.py`
- [X] T015 [P] [US2] Add failing test for summary failure producing `summary_failed` with useful reason text in `apps/api/tests/test_agentic_research.py`
- [X] T016 [P] [US2] Add failing test for evidence insufficiency producing `evidence_insufficient` in `apps/api/tests/test_agentic_research.py`
- [X] T017 [P] [US2] Add failing report response contract test for all refined reason codes and server-provided reason text in `apps/api/tests/test_research_report.py`

### Implementation for User Story 2

- [X] T018 [US2] Update `AgenticResearchStore.report_exclusions` in `apps/api/app/agentic_research/store.py` to classify non-403 unreachable sources as `unreachable`
- [X] T019 [US2] Update `AgenticResearchStore.report_exclusions` in `apps/api/app/agentic_research/store.py` to preserve summary failure and evidence-insufficient explanations without relevance wording
- [X] T020 [US2] Update stored reason text in `apps/api/app/agentic_research/store.py` so every exclusion category uses concise operator-facing business language
- [X] T021 [US2] Run the focused US2 tests in `apps/api/tests/test_agentic_research.py` and `apps/api/tests/test_research_report.py`

**Checkpoint**: User Story 2 should make every exclusion category
operator-readable and distinct.

---

## Phase 5: User Story 3 - Preserve Existing Report Workflow (Priority: P3)

**Goal**: The correction does not change report inclusion, report findings,
workflow status, model prompts, trust decisions, or source eligibility.

**Independent Test**: Existing report generation tests still pass, and the same
qualified supporting sources remain included while only exclusion reason labels
change.

### Tests for User Story 3

- [X] T022 [P] [US3] Add regression test that supporting-source inputs are unchanged when exclusion reason labels change in `apps/api/tests/test_agentic_research_reporting.py`
- [X] T023 [P] [US3] Add regression test that `ResearchReportingService.final_report` still obtains exclusions from `AgenticResearchStore.report_exclusions` without model-authored reasons in `apps/api/tests/test_agentic_research_reporting.py`

### Implementation for User Story 3

- [X] T024 [US3] Inspect `apps/api/app/agentic_research/reporting.py` and preserve the existing exclusion retrieval path without adding model-authored reason generation
- [X] T025 [US3] Add or update a UI-facing verification in `apps/web/src/App.tsx` or existing web test coverage to prove the Final report panel renders the server-provided `reason` text without client-side inference
- [X] T026 [US3] Run existing report tests in `apps/api/tests/test_agentic_research_reporting.py`

**Checkpoint**: All user stories should be independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, final validation, and implementation hygiene.

- [X] T027 [P] Review `specs/008-fix-exclusion-labels/quickstart.md` after implementation and update it so the manual verification wording matches the final reason text
- [X] T028 [P] Review `specs/008-fix-exclusion-labels/contracts/report-exclusion-contract.md` after implementation and update it so the documented reason codes and wording match the final contract
- [X] T029 Run API lint and focused tests for `apps/api/app/agentic_research/store.py`, `apps/api/tests/test_agentic_research.py`, `apps/api/tests/test_agentic_research_reporting.py`, and `apps/api/tests/test_research_report.py`
- [X] T030 Run full API tests if focused tests pass
- [X] T031 Run `npm run build` in `apps/web` after completing the UI-facing verification task
- [X] T032 Run `git diff --check`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup completion and blocks all user stories.
- **User Story 1 (Phase 3)**: Depends on Foundation; MVP scope.
- **User Story 2 (Phase 4)**: Depends on Foundation; can be developed after or alongside US1 if helper mapping is stable.
- **User Story 3 (Phase 5)**: Depends on US1 and US2 behavior enough to assert preservation.
- **Polish (Phase 6)**: Depends on completed desired user stories.

### User Story Dependencies

- **US1**: Can start after Phase 2. Delivers the main bug fix.
- **US2**: Can start after Phase 2. Adds complete category coverage.
- **US3**: Should run after US1 and US2 implementation because it verifies unchanged report workflow behavior.

### Parallel Opportunities

- T003 and T005-T006 can run in parallel after T001-T002.
- T007-T009 can be written in parallel.
- T014-T017 can be written in parallel.
- T022-T023 can be written in parallel.
- T027-T028 can be completed in parallel with final validation if wording is stable.

---

## Parallel Example: User Story 1

```text
Task: "Add failing test for publisher access denial producing access_denied_by_publisher in apps/api/tests/test_agentic_research.py"
Task: "Add failing test for local trust block producing blocked_by_trust_policy in apps/api/tests/test_agentic_research.py"
Task: "Add failing test proving not_relevant_to_planned_topics is used only after usable summarized evidence exists in apps/api/tests/test_agentic_research.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 and Phase 2.
2. Implement US1 tests and report exclusion derivation.
3. Validate that blocked extraction no longer appears as topic irrelevance.
4. Stop and review if the implementation requires new stored fields or UI inference.

### Incremental Delivery

1. US1 fixes the misleading label for extraction-blocked sources.
2. US2 completes the full exclusion category set.
3. US3 proves the report workflow and report findings were not changed.
4. Polish updates docs/contracts only if implementation wording differs.

## Notes

- `[P]` tasks touch different files or independent test cases.
- Every user-story task has an exact file path.
- Do not add another report workflow, model prompt, UI inference path, trust rule, or Temporal workflow.
- Existing historical reports remain historical snapshots; this feature affects newly generated report packages.
