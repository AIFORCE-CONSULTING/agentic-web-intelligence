# Tasks: Bounded Final Report Batching

**Input**: Design documents from `specs/009-bounded-report-batching/`  
**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`

**Tests**: Required. This feature changes report-generation behavior, model-output validation, report-attempt persistence, and operator-visible report quality. Tests must be written before implementation tasks in each story phase.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Phase 1: Setup

**Purpose**: Confirm active feature context and current report path before implementation.

- [X] T001 Verify `.specify/feature.json` points to `specs/009-bounded-report-batching` and `AGENTS.md` points to `specs/009-bounded-report-batching/plan.md`
- [X] T002 Inspect current report-generation code in `apps/api/app/agentic_research/reporting.py`, `apps/api/app/agentic_research/store.py`, and `apps/api/app/agentic_research/contracts.py`
- [X] T003 [P] Inspect existing report tests in `apps/api/tests/test_agentic_research_reporting.py` and `apps/api/tests/test_research_report.py`

---

## Phase 2: Foundational

**Purpose**: Add shared persistence and contract support required by all user stories.

**Critical**: No user story implementation should begin until this phase is complete.

- [X] T004 Add `group_index` and `response_characters` to `FinalReportAttempt` in `apps/api/app/agentic_research/contracts.py`
- [X] T005 Add `group_index`, `response_characters`, and uniqueness by report/topic/group/attempt in `apps/api/app/agentic_research/store.py`
- [X] T006 Update `AgenticResearchStore.save_report_package` in `apps/api/app/agentic_research/store.py` to persist bounded group attempt identity and response character counts
- [X] T007 Update stored report attempt loading/assertion helpers in `apps/api/tests/test_agentic_research_reporting.py`
- [X] T008 [P] Add store/API regression coverage for report attempts with multiple groups and recorded response character counts in `apps/api/tests/test_agentic_research_reporting.py`

**Checkpoint**: Report attempts can identify the bounded group that produced them.

---

## Phase 3: User Story 1 - Generate a Report for Large Topic Evidence (Priority: P1)

**Goal**: A topic with many qualified summaries is processed in bounded groups and produces useful validated findings instead of failing only because one topic payload was too large.

**Independent Test**: A test run with one topic and 15 qualified summaries produces multiple bounded model calls, merges accepted findings, and stores a report with findings for that topic.

### Tests for User Story 1

- [X] T009 [P] [US1] Add failing test for splitting 15 topic summaries into bounded report groups in `apps/api/tests/test_agentic_research_reporting.py`
- [X] T010 [P] [US1] Add failing test proving accepted findings from multiple bounded groups merge into one topic section in `apps/api/tests/test_agentic_research_reporting.py`
- [X] T011 [P] [US1] Add failing test proving every qualified source remains in the deterministic topic source list after grouping in `apps/api/tests/test_agentic_research_reporting.py`
- [X] T012 [P] [US1] Add failing test proving grouping honors the prompt character budget and isolates a single oversized summary in `apps/api/tests/test_agentic_research_reporting.py`

### Implementation for User Story 1

- [X] T013 [US1] Add bounded report group planning helpers in `apps/api/app/agentic_research/reporting.py` using maximum seven summaries per group and approximately 10,000 prompt input characters per group
- [X] T014 [US1] Change `ResearchReportingService.final_report` in `apps/api/app/agentic_research/reporting.py` to draft findings per bounded group instead of per whole topic
- [X] T015 [US1] Merge accepted bounded group findings into one `TopicSectionResult` per planned topic in `apps/api/app/agentic_research/reporting.py`
- [X] T016 [US1] Preserve full topic source-list contributions for all topic inputs in `apps/api/app/agentic_research/reporting.py`
- [X] T017 [US1] Run focused report tests for US1 with `pytest -q apps/api/tests/test_agentic_research_reporting.py`

**Checkpoint**: User Story 1 should be independently functional and testable.

---

## Phase 4: User Story 2 - Preserve Platform-Owned Report Structure (Priority: P2)

**Goal**: Batching must not give the model control over report sections, source assignment, citation links, or source lists.

**Independent Test**: A bounded group that cites an out-of-group source is rejected, while valid group citations render as platform-owned links to stored summaries.

### Tests for User Story 2

- [X] T018 [P] [US2] Add failing test rejecting citations outside the current bounded group in `apps/api/tests/test_agentic_research_reporting.py`
- [X] T019 [P] [US2] Add failing test normalizing harmless in-group citation variants only in `apps/api/tests/test_agentic_research_reporting.py`
- [X] T020 [P] [US2] Add failing API response test proving report links and source lists remain deterministic in `apps/api/tests/test_research_report.py`

### Implementation for User Story 2

- [X] T021 [US2] Scope `_assess_topic_draft` validation to the current bounded group in `apps/api/app/agentic_research/reporting.py`
- [X] T022 [US2] Scope `_normalized_findings` citation normalization to the current bounded group in `apps/api/app/agentic_research/reporting.py`
- [X] T023 [US2] Ensure `_render_topic_sections` still renders one planned topic section with one deterministic full-topic source list in `apps/api/app/agentic_research/reporting.py`
- [X] T024 [US2] Run focused report tests for US2 with `pytest -q apps/api/tests/test_agentic_research_reporting.py apps/api/tests/test_research_report.py`

**Checkpoint**: User Story 2 should preserve platform-owned report structure.

---

## Phase 5: User Story 3 - Explain Report Quality Clearly (Priority: P3)

**Goal**: Report quality should distinguish complete, partially degraded, and fallback report outcomes without confusing report-stage problems with search, trust, extraction, relevance, or summary failures.

**Independent Test**: A topic with one successful bounded group and one failed bounded group still renders successful findings, stores a `FAIL` quality grade, and records a concise bounded-group quality reason.

### Tests for User Story 3

- [X] T025 [P] [US3] Add failing test proving `{}` is recorded as invalid empty findings with group-specific telemetry and response character count in `apps/api/tests/test_agentic_research_reporting.py`
- [X] T026 [P] [US3] Add failing test proving one failed bounded group does not erase successful findings from another group in `apps/api/tests/test_agentic_research_reporting.py`
- [X] T027 [P] [US3] Add failing test proving all failed groups for a topic produce stored-evidence fallback for that topic in `apps/api/tests/test_agentic_research_reporting.py`
- [X] T028 [P] [US3] Add failing API response test for partial report quality reasons in `apps/api/tests/test_research_report.py`
- [X] T029 [P] [US3] Verify the existing Final report UI displays report-stage quality reasons distinctly from search, extraction, trust, relevance, and summary failures in `apps/web/src/App.tsx`

### Implementation for User Story 3

- [X] T030 [US3] Require non-empty `findings` in `TopicFindingDraft` in `apps/api/app/agentic_research/contracts.py`
- [X] T031 [US3] Add explicit empty-output failure classification and retry feedback in `apps/api/app/agentic_research/reporting.py`
- [X] T032 [US3] Record group-specific quality reasons without discarding accepted findings in `apps/api/app/agentic_research/reporting.py`
- [X] T033 [US3] Ensure report origin is `model_fail` when at least one bounded group succeeds and at least one group fails in `apps/api/app/agentic_research/reporting.py`
- [X] T034 [US3] Run focused report tests for US3 with `pytest -q apps/api/tests/test_agentic_research_reporting.py apps/api/tests/test_research_report.py`

**Checkpoint**: User Story 3 should provide useful partial reports and clear report-stage explanations.

---

## Phase 6: Polish and Cross-Cutting

**Purpose**: Documentation, runtime observation, and full validation.

- [X] T035 [P] Update `docs/local-evidence-intelligence.md` final report quality section to describe bounded report groups and partial degradation
- [X] T036 [P] Update ADR 0014 final-report package notes in `docs/adr/0014-governed-local-model-provider.md`
- [X] T037 [P] Update ADR 0016 final-report workflow notes in `docs/adr/0016-governed-local-agent-capability-requests.md`
- [X] T038 Review `specs/009-bounded-report-batching/quickstart.md` runtime observation notes for `keep_alive`, `num_ctx`, loaded-model count, and parallelism; update only if implementation changes what operators should observe
- [X] T039 Run full API validation with `ruff check . && PYTHONPATH=/workspace/apps/api pytest -q` from `apps/api`
- [X] T040 Run web build with `npm run build` from `apps/web` if T029 changes report quality display labels or behavior
- [X] T041 Run `git diff --check`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 Setup**: No dependencies.
- **Phase 2 Foundational**: Depends on Phase 1 and blocks all user stories.
- **Phase 3 US1**: Depends on Phase 2.
- **Phase 4 US2**: Depends on Phase 2; can begin after bounded group structures exist, but should be validated after US1 merge behavior.
- **Phase 5 US3**: Depends on Phase 2; can begin after bounded group attempt identity exists, but final semantics should be validated after US1 merge behavior.
- **Phase 6 Polish**: Depends on desired user stories being complete.

### User Story Dependencies

- **US1** is the MVP and should be implemented first.
- **US2** can proceed after foundational group persistence, but depends conceptually on the bounded group validator introduced by US1.
- **US3** can proceed after foundational group persistence, but depends conceptually on the bounded group attempt and merge behavior introduced by US1.

### Parallel Opportunities

- T003 can run in parallel with T002.
- T008 can run after T004-T006 are planned but before implementation is finished as a failing regression test.
- T009-T012 can be written in parallel.
- T018-T020 can be written in parallel.
- T025-T029 can be written in parallel.
- T035-T037 can be written in parallel after implementation behavior is settled.

---

## Parallel Example: User Story 1

```text
Task: "Add failing test for splitting 15 topic summaries into bounded report groups in apps/api/tests/test_agentic_research_reporting.py"
Task: "Add failing test proving accepted findings from multiple bounded groups merge into one topic section in apps/api/tests/test_agentic_research_reporting.py"
Task: "Add failing test proving every qualified source remains in the deterministic topic source list after grouping in apps/api/tests/test_agentic_research_reporting.py"
```

---

## Implementation Strategy

### MVP First

1. Complete Phase 1 and Phase 2.
2. Complete Phase 3 only.
3. Validate that one large topic can be split into bounded groups and still produce a useful topic section.
4. Stop for review if the bounded grouping changes report quality semantics unexpectedly.

### Incremental Delivery

1. Add bounded report group persistence.
2. Add large-topic group drafting and merge behavior.
3. Add strict group-scoped citation validation.
4. Add partial-degradation quality explanations.
5. Update docs and run full validation.

### Notes

- Do not add a new report route, report button, Temporal workflow, MCP tool, or LangGraph path.
- Keep `ResearchReportingService.final_report` as the only report-generation owner.
- Keep model output untrusted until deterministic validation passes.
- Commit after a cohesive task group, not necessarily after every individual task.
