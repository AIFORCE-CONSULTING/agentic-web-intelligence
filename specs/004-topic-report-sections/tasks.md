# Tasks: Topic-Scoped Report Sections

**Input**: Design documents from `specs/004-topic-report-sections/`
**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/topic-report-contract.md`, `quickstart.md`

**Tests**: Required. This feature changes model contracts, report rendering, and operator-visible output, so task slices include targeted unit, integration, and UI/build verification.

**Organization**: Tasks are grouped by user story so each story can be implemented and validated independently.

## Phase 1: Setup (Shared Context)

**Purpose**: Establish the shared fixtures and vocabulary used by all report-section work.

- [X] T001 Review existing final-report tests and add reusable multi-topic fixtures with planned topics, qualified summaries, and exclusions in `apps/api/tests/test_agentic_research_reporting.py`
- [X] T002 [P] Add topic-scoped report contract constants and prompt-version naming for topic-level findings in `apps/api/app/agentic_research/reporting.py`
- [X] T003 [P] Add or update type aliases for topic-scoped report finding status, citation-label failure codes, and topic-section quality reason codes in `apps/api/app/agentic_research/contracts.py`
- [X] T004 [P] Update final-report planning notes in `docs/adr/0014-governed-local-model-provider.md` to describe platform-owned sections and model-owned topic findings
- [X] T005 [P] Update final-report workflow wording in `docs/adr/0016-governed-local-agent-capability-requests.md` to clarify that the existing LangGraph final-report node remains the sole caller

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Add deterministic citation-label and topic-section helpers that every story depends on.

**Critical**: No user story implementation should proceed until these helpers and tests exist.

- [X] T006 Add tests for `S01`-style label assignment, stable report-input ordering, and old `source-01` behavior replacement in `apps/api/tests/test_agentic_research_reporting.py`
- [X] T007 Implement simple `S01` citation-label assignment in `AgenticResearchStore.report_inputs` in `apps/api/app/agentic_research/store.py`
- [X] T008 Add table-driven tests for harmless citation-label normalization, including lowercase labels, harmless spacing, missing leading zero variants such as `S1`, and invalid ambiguous labels that must still be rejected, in `apps/api/tests/test_agentic_research_reporting.py`
- [X] T009 Implement deterministic citation-label normalization and rejection helpers in `apps/api/app/agentic_research/reporting.py`
- [X] T010 Add tests proving unknown, ambiguous, and cross-topic citation labels are rejected in `apps/api/tests/test_agentic_research_reporting.py`
- [X] T011 Update report-input and attempt diagnostics to preserve topic scope for per-topic attempts in `apps/api/app/agentic_research/contracts.py`
- [X] T012 Extend report-attempt persistence with explicit topic-scoped diagnostics in `apps/api/app/agentic_research/store.py`, including a nullable `topic_id` for historical whole-report attempts and uniqueness for new topic attempts on `report_id`, `topic_id`, and `attempt_number`

**Checkpoint**: The platform can assign and validate simple citation labels without invoking a model or changing workflow status.

---

## Phase 3: User Story 1 - Receive A Consistent Grounded Report (Priority: P1)

**Goal**: Generate a final report whose sections are created from stored planned topics, while the model drafts findings for one supplied topic at a time.

**Independent Test**: Run reporting with three planned topics and qualified summaries; the stored Markdown contains exactly those planned sections in order, with no section created from legacy or unexpected model-authored topic fields.

### Tests for User Story 1

- [X] T013 [P] [US1] Add a failing unit test for per-topic prompt payloads containing only one topic and that topic's source summaries in `apps/api/tests/test_agentic_research_reporting.py`
- [X] T014 [P] [US1] Add a failing unit test that legacy or unexpected model-authored topic fields cannot create, rename, reorder, or omit planned report sections in `apps/api/tests/test_agentic_research_reporting.py`
- [X] T015 [P] [US1] Add a failing integration test that the existing LangGraph final-report node stores a report package from topic-scoped drafts in `apps/api/tests/test_unified_research_integration.py`

### Implementation for User Story 1

- [X] T016 [US1] Replace the whole-report draft schema with a topic-finding draft schema in `apps/api/app/agentic_research/contracts.py`
- [X] T017 [US1] Replace whole-report payload construction with per-topic payload construction in `apps/api/app/agentic_research/reporting.py`
- [X] T018 [US1] Update `ResearchReportingService.final_report` to iterate planned topics and call the local model once per topic attempt in `apps/api/app/agentic_research/reporting.py`
- [X] T019 [US1] Implement platform-owned planned-section rendering for topic headings and insufficient-evidence sections in `apps/api/app/agentic_research/reporting.py`
- [X] T020 [US1] Update draft assessment so legacy or unexpected model-authored topic identifiers are rejected or ignored safely, rendered topics always come from stored planned topics, and topic coverage is evaluated from stored planned topics in `apps/api/app/agentic_research/reporting.py`
- [X] T021 [US1] Preserve the existing `generate_final_report` LangGraph node and update only its expectations/tests for topic-scoped report packages in `apps/api/app/agentic_research/workflow_nodes.py`
- [X] T022 [US1] Run focused reporting and workflow tests for User Story 1 with `pytest` in `apps/api/tests/test_agentic_research_reporting.py`, `apps/api/tests/test_unified_research_integration.py`, and `apps/api/tests/test_unified_research_workflow.py`

**Checkpoint**: User Story 1 is complete when the report can be generated with platform-owned sections and no model-owned topic structure.

---

## Phase 4: User Story 2 - Understand Report Quality Problems (Priority: P2)

**Goal**: Make report-quality failures explain unsupported citations, malformed topic output, timeouts, unavailable models, and insufficient topic evidence in operator-readable language.

**Independent Test**: Force malformed topic output, unsupported labels, and model timeout; the stored report or fallback briefing contains concise `FAIL` reasons and the run completes when the package is stored.

### Tests for User Story 2

- [X] T023 [P] [US2] Add failing tests for unsupported citation-label quality reasons in `apps/api/tests/test_agentic_research_reporting.py`
- [X] T024 [P] [US2] Add failing tests for malformed topic output, legacy or unexpected model-authored topic identifiers, and unavailable-model topic fallback in `apps/api/tests/test_agentic_research_reporting.py`
- [X] T025 [P] [US2] Add API response tests proving report quality reasons remain visible through `GET /v1/research/runs/{run_id}/report` in `apps/api/tests/test_research_report.py`

### Implementation for User Story 2

- [X] T026 [US2] Add topic-specific quality reason codes and messages for unsupported citations, malformed topic output, model timeout, and insufficient topic evidence in `apps/api/app/agentic_research/contracts.py`
- [X] T027 [US2] Record topic-specific validation errors, duration, input size, and failure code for each bounded topic attempt in `apps/api/app/agentic_research/reporting.py`
- [X] T028 [US2] Render operator-readable `FAIL` reasons for partial topic fallback and unsupported labels in `apps/api/app/agentic_research/reporting.py`
- [X] T029 [US2] Ensure unreadable report inputs or failed report persistence still fail the research run while model failures produce stored `FAIL` reports in `apps/api/app/agent_runtime/research_workflow.py`
- [X] T030 [US2] Update report endpoint tests and response examples for topic-scoped failure reasons in `apps/api/tests/test_research_report.py`

**Checkpoint**: User Story 2 is complete when the operator can understand why a report passed, failed, or fell back without reading logs.

---

## Phase 5: User Story 3 - Preserve Traceability Without Overburdening The Model (Priority: P3)

**Goal**: Keep source traceability while trusted platform code owns source lists, citation links, and stored-summary navigation.

**Independent Test**: Inspect a completed report; citation links and topic source lists are rendered from stored source mappings, and the model never supplies navigation targets.

### Tests for User Story 3

- [X] T031 [P] [US3] Add failing tests that citation links are rendered only from stored `ReportSupportingSource` mappings in `apps/api/tests/test_agentic_research_reporting.py`
- [X] T032 [P] [US3] Add failing tests that each topic renders all qualified topic sources in a source list even when some are not cited by findings in `apps/api/tests/test_agentic_research_reporting.py`
- [X] T033 [P] [US3] Add or update UI/build checks for simple citation labels and topic source-list links in `apps/web/src/App.tsx`

### Implementation for User Story 3

- [X] T034 [US3] Render citation Markdown from normalized stored labels and summary anchors in `apps/api/app/agentic_research/reporting.py`
- [X] T035 [US3] Render deterministic topic-level source lists for all qualified topic inputs in `apps/api/app/agentic_research/reporting.py`
- [X] T036 [US3] Update supporting-source maps and report currentness behavior for `S01` labels in `apps/api/app/agentic_research/store.py`
- [X] T037 [US3] Update the existing Final report panel to display `S01`-style citations and topic source lists without allowing model-authored links in `apps/web/src/App.tsx`
- [X] T038 [US3] Run focused API report tests and the web build for traceability behavior in `apps/api/tests/test_agentic_research_reporting.py` and `apps/web/package.json`

**Checkpoint**: User Story 3 is complete when every visible citation and topic source link is derived from stored platform data.

---

## Phase 6: Polish & Cross-Cutting Verification

**Purpose**: Documentation, regression coverage, and final verification across the complete report workflow.

- [X] T039 [P] Update `docs/local-evidence-intelligence.md` with operator-facing wording for topic-scoped report sections, simple citation labels, and fallback reports
- [X] T040 [P] Update `ROADMAP.md` to mark topic-scoped report sections as the active report-quality refinement
- [X] T041 [P] Update `specs/004-topic-report-sections/quickstart.md` with any final manual verification adjustments discovered during implementation
- [X] T042 Add regression tests for stale report currentness and historical report readability after `S01` label adoption in `apps/api/tests/test_agentic_research_reporting.py`
- [X] T043 Add an integration or regression fixture with at least ten qualified summaries across planned topics and verify the stored report is either `PASS` or a visible `FAIL` report that still renders topic-organized evidence in `apps/api/tests/test_agentic_research_reporting.py`
- [X] T044 Run full API lint and test suite using `apps/api/requirements-dev.lock`
- [X] T045 Run web TypeScript/Vite build using `apps/web/package.json`
- [X] T046 Run `git diff --check` and verify no generated artifact points Spec Kit at the wrong feature in `.specify/feature.json` and `AGENTS.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 Setup**: No dependencies.
- **Phase 2 Foundational**: Depends on Phase 1 and blocks all user stories.
- **Phase 3 / US1**: Depends on Phase 2. This is the MVP.
- **Phase 4 / US2**: Depends on Phase 2 and can begin after US1 contracts are stable; final validation depends on US1 report flow.
- **Phase 5 / US3**: Depends on Phase 2 and can begin after US1 rendering shapes are stable; final UI validation depends on US1/US2 report output.
- **Phase 6 Polish**: Depends on selected user stories being complete.

### User Story Dependencies

- **US1**: Required MVP. Establishes topic-owned report structure.
- **US2**: Builds on US1 output to improve explanation of failures.
- **US3**: Builds on US1 output to polish traceability and UI links.

### Parallel Opportunities

- T002-T005 can run in parallel after T001.
- T013-T015 can run in parallel once Phase 2 is done.
- T023-T025 can run in parallel once US1 contracts are stable.
- T031-T033 can run in parallel once US1 rendering shapes are stable.
- Documentation tasks T039-T041 can run in parallel after implementation behavior is stable.

## Parallel Example: User Story 1

```text
Task: "Add a failing unit test for per-topic prompt payloads containing only one topic and that topic's source summaries in apps/api/tests/test_agentic_research_reporting.py"
Task: "Add a failing unit test that a model response cannot create, rename, reorder, or omit planned report sections in apps/api/tests/test_agentic_research_reporting.py"
Task: "Add a failing integration test that the existing LangGraph final-report node stores a report package from topic-scoped drafts in apps/api/tests/test_research_workflow.py"
```

## Implementation Strategy

### MVP First

1. Complete Phase 1 and Phase 2.
2. Complete Phase 3 / US1.
3. Stop and validate that platform-owned planned sections and topic-scoped model calls work independently.

### Incremental Delivery

1. US1: make the report consistently render planned topic sections.
2. US2: improve quality explanations and fallback reporting.
3. US3: complete citation and source-list traceability in API/UI.
4. Polish: docs, roadmap, full verification.

## Notes

- `[P]` tasks touch different files or can be done independently after prerequisites.
- Tests are intentionally first within each story because this feature tightens model contracts.
- Do not introduce a new report workflow, report-start endpoint, Temporal report workflow, MCP capability, or source-eligibility decision.
