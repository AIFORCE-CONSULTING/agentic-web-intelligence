# Tasks: Grounded Final Reports

**Input**: Design documents from specs/003-improve-final-report  
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/final-report-api.md, and quickstart.md

## Format

Each task follows the required checklist format: checkbox, sequential ID, optional
parallel marker, user-story label where applicable, an actionable description, and
exact file paths.

## Phase 1: Setup

**Purpose**: Establish test fixtures and shared report-contract vocabulary without changing the research workflow.

- [x] T001 Create deterministic qualified-source, planned-topic, exclusion, and malformed-report fixtures in apps/api/tests/test_agentic_research_reporting.py
- [x] T002 [P] Add report contract version constants, PASS/FAIL grade constants, fallback-report origin, and operator-safe infrastructure failure types in apps/api/app/agentic_research/reporting.py
- [x] T003 [P] Add report draft, report package, PASS/FAIL quality grade, typed quality-reason code/message objects including model_unavailable, malformed_model_response, and unsafe_model_draft, fixed report-origin enum, supporting-source, exclusion, fallback-origin, and attempt Pydantic contracts in apps/api/app/agentic_research/contracts.py

## Phase 2: Foundational Data and Validation

**Purpose**: Add immutable report provenance records and the deterministic validator needed by every user story.

- [x] T004 Add append-only report-attempt, report-input, report-contribution, and report-exclusion schema changes plus indexes in apps/api/app/agentic_research/store.py
- [x] T005 Add transactional store methods that create a report attempt, save a PASS or FAIL report package with child provenance rows, and preserve attempt diagnostics in apps/api/app/agentic_research/store.py
- [x] T006 Implement the deterministic final-report validator that separates structural safety from report quality: require valid schema, at least one known topic-scoped source reference for every factual finding, and no findings in insufficient sections before rendering; then score three equal-weight checks—planned-topic coverage, qualified-source representation, and applicable narrative length—in apps/api/app/agentic_research/reporting.py
- [x] T007 Add unit tests for report-attempt persistence, immutable input snapshots, and every validator rejection reason in apps/api/tests/test_agentic_research_reporting.py
- [ ] T008 Add wrong-workspace, invalid-run, retry/idempotency, and stale-input integration coverage for report persistence in apps/api/tests/test_agentic_research_reporting.py

**Checkpoint**: The platform can persist a validated report package or a diagnostic rejected attempt without changing eligibility, trust, relevance, coverage, or workflow status.

## Phase 3: User Story 1 - Receive a Complete Evidence-Grounded Report (Priority: P1)

**Goal**: Generate a detailed evidence-grounded report that covers every planned topic and qualified source when possible, uses one bounded correction when the first draft is incomplete, and always gives the operator a report with a visible PASS or FAIL quality grade when inputs can be read and stored.

**Independent Test**: Use qualified summaries across technical, user-experience, ethical, commercial, and operational topics. Verify every planned topic and qualified source is represented; verify one malformed first draft is corrected; verify two malformed drafts produce a FAIL fallback briefing while the run completes and source summaries remain available.

- [x] T009 [US1] Extend qualified report-input loading to create stable source references, source title fallbacks, summary snapshots, topic associations, and a deterministic input fingerprint in apps/api/app/agentic_research/store.py
- [x] T010 [US1] Replace free-form final-report prompting with an Ollama native JSON-schema prompt that supplies only the fixed qualified report input and treats summaries as untrusted data in apps/api/app/agentic_research/reporting.py
- [x] T011 [US1] Implement two-attempt report drafting: record attempt one, send precise validation feedback only after a non-passing assessment, record attempt two, and retain both attempt results in apps/api/app/agentic_research/reporting.py
- [x] T012 [US1] Render passing drafts, highest-scoring structurally safe failing drafts, and platform fallback evidence briefings into Markdown with every planned topic, insufficient-evidence disclosure, source-reference placeholders, PASS or FAIL grade, and concise quality reasons in apps/api/app/agentic_research/reporting.py
- [x] T013 [US1] Preserve ResearchStore as the only status writer and make reporting complete after any report package is stored; reserve report-stage workflow failure for unreadable inputs or an unsaved report package in apps/api/app/agent_runtime/research_workflow.py
- [ ] T014 [US1] Keep the existing LangGraph final-report node as the sole report caller and add passing-grade, failing-grade, fallback, and true-storage-failure integration tests in apps/api/app/agentic_research/workflow_nodes.py and apps/api/tests/test_research_workflow.py
- [ ] T015 [US1] Add reporting-service tests for complete multi-topic reports, unique source findings, source-role fixtures, word-target enforcement, one successful correction, best-usable FAIL selection, and fallback evidence briefings in apps/api/tests/test_agentic_research_reporting.py

**Checkpoint**: A PASS report meets deterministic quality checks. A readable but incomplete model answer receives a FAIL grade with reasons; it does not hide the evidence or prevent the run from completing. A fallback briefing is used when no model answer is usable.

## Phase 4: User Story 2 - Trace Report Claims to Stored Sources (Priority: P1)

**Goal**: Let the operator open the stored source summary that supports each report finding, while preventing model-generated links from becoming navigation targets.

**Independent Test**: Generate a report with one and several supporting sources per finding. In the UI, select each attribution and section source-list entry and verify it opens the matching stored summary without opening an external URL.

- [x] T016 [US2] Extend report retrieval to load the stored report package, immutable supporting-source map, contribution data, exclusions, quality grade, and currentness checks in apps/api/app/agentic_research/store.py
- [x] T017 [US2] Extend the existing report endpoint response and workspace-scoped error handling with report quality grade, reasons, and origin without adding a report-start endpoint in apps/api/app/main.py
- [ ] T018 [US2] Add API contract tests for report source maps, PASS and FAIL reports, fallback reports, historical/stale-report behavior, and cross-workspace denial in apps/api/tests/test_main.py
- [x] T019 [US2] Extend report TypeScript types and render a visible PASS or FAIL quality badge, report origin, typed quality reasons, and only platform-produced stored-summary attribution and section-source-list links using the existing selected-summary behavior in apps/web/src/App.tsx
- [x] T020 [US2] Add safe link-rendering checks and build coverage for report Markdown in apps/web/src/App.tsx and apps/web/package.json

**Checkpoint**: The report shows evidence traceability in the existing UI, and no model response can create an arbitrary clickable destination.

## Phase 5: User Story 3 - Understand What the Report Did Not Use (Priority: P2)

**Goal**: Clearly disclose completed and noncontributing sources, their assessed topics, and concise recorded reasons while keeping them outside automated report evidence.

**Independent Test**: Use a run containing a completed but nonqualified source, an evidence-insufficient source, and a blocked or review-required source. Verify each is separate from supporting sources and names its recorded reason.

- [x] T021 [US3] Build deterministic exclusion records from existing summary, relevance, trust, and human-review outcomes, including assessed topics and concise operator-readable reasons, in apps/api/app/agentic_research/store.py
- [x] T022 [US3] Render server-generated exclusions outside model output and attach them to the accepted immutable report package in apps/api/app/agentic_research/reporting.py
- [x] T023 [US3] Render the separate exclusion disclosure in the existing Final report panel without presenting excluded sources as report support in apps/web/src/App.tsx
- [ ] T024 [US3] Add API and reporting tests for completed-not-relevant, blocked, review-required, insufficient, and summary-failed exclusions in apps/api/tests/test_agentic_research_reporting.py and apps/api/tests/test_main.py

**Checkpoint**: The operator can see what the report did not use and why, without mistaking it for supporting evidence.

## Phase 6: Documentation, Migration, and Verification

**Purpose**: Make the report contract understandable, preserve architecture alignment, and prove the complete change through the actual owners.

- [x] T025 Amend final-report governance, provenance, bounded correction, and report-input restrictions in docs/adr/0014-governed-local-model-provider.md
- [x] T026 Update final-report workflow wording and current implementation status in docs/adr/0016-governed-local-agent-capability-requests.md
- [x] T027 Update phase and roadmap language for validated grounded reports in docs/roadmap.md
- [x] T028 Add an operator-facing explanation of report sources, exclusions, correction behavior, PASS or FAIL report quality grades, fallback briefings, and true report-storage failure in docs/local-evidence-intelligence.md
- [ ] T029 Add migration coverage proving historical report rows remain readable as historical data and cannot be represented as a current validated report in apps/api/tests/test_agentic_research_reporting.py
- [x] T030 Run focused API reporting/workflow tests, the full API suite, Ruff, and the web TypeScript/Vite build using apps/api/requirements-dev.lock and apps/web/package.json

## Dependencies and Execution Order

    Phase 1: T001-T003
        |
    Phase 2: T004-T008
        |
        +--> US1: T009-T015
        |        |
        |        +--> US2: T016-T020
        |        |
        |        +--> US3: T021-T024
        |
    Phase 6: T025-T030

- US1 requires the shared persistence and validator work from Phase 2.
- US2 requires an accepted structured report package from US1.
- US3 can start its store-query work after T004-T005, but its UI presentation joins the stored report package from US1; it therefore completes after US1.
- Documentation and full verification complete after all user stories.

## Parallel Opportunities

- T002 and T003 touch different files and may proceed in parallel.
- After T004, T006 can begin while T005 implements store write methods.
- T018 can begin after the response shape is agreed in T003, while T016 implements store retrieval.
- T021 can begin after T004-T005 while US2 UI work proceeds.
- T025-T028 can proceed in parallel after the implementation behavior is settled.

## Implementation Strategy

1. **MVP:** Complete Phases 1-3. This prevents partial or unsupported final reports from being accepted, without adding an operator workflow.
2. **Traceability:** Complete Phase 4 so every report finding can lead to an existing stored source summary.
3. **Scope transparency:** Complete Phase 5 so operators can understand exclusions.
4. **Finish safely:** Complete Phase 6 with documentation, migration checks, and the full verification suite.

## Format Validation

All 30 tasks use the required checkbox, task ID, optional parallel marker, story label where applicable, concrete description, and file path format.
