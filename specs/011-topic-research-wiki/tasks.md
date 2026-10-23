# Tasks: Topic Research Wiki

**Input**: Design documents from `specs/011-topic-research-wiki/`  
**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md),
[data-model.md](data-model.md), [topic-research-api.md](contracts/topic-research-api.md)

**Tests**: This feature changes durable business records, a governed workflow,
model-grounded reporting, and operator-facing behavior. Persistence, API,
workflow, and UI tests are required.

**Organization**: Tasks are grouped by user story. User Story 1 is the MVP;
User Story 2 depends on its topic/run foundation, while User Stories 3 and 4
extend the resulting topic workspace.

## Phase 1: Documentation and Approval Preparation

**Purpose**: Record the lasting architectural change and make the required
implementation approval checkpoint easy to review.

- [X] T001 [P] Draft ADR 0017 in `docs/adr/0017-topic-centered-research-notebook.md`, amending ADR 0016 to define Research Topics, topic-scoped question reuse, and revision-owned wiki publication.
- [X] T002 [P] Update `ROADMAP.md`, `docs/current-platform-architecture.md`, and `docs/architecture-glossary.md` with the topic notebook boundary and the distinction between Research Topics and Planned Topics.
- [X] T003 [P] Update `docs/local-evidence-intelligence.md` and `docs/agent-runtime.md` so operator documentation describes topic-centered research, retained authority boundaries, and read-only Studio.
- [X] T004 Record the approved State and Decision Ownership Matrix and the design-alignment approval in `specs/011-topic-research-wiki/plan.md` before any runtime, database, API, or UI task starts.

**Checkpoint**: The operator has explicitly approved clean-start retirement of
standalone reports, topic-scoped question reuse, extension of the unified graph,
the reporting-service ownership of wiki revisions, and operator-question-only
research entry for this release.

---

## Phase 2: Foundational Topic Records and Contracts

**Purpose**: Create the durable topic boundary and typed contracts that every
story uses, without creating a competing run lifecycle or authority path.

- [X] T005 Add Research Topic, topic-run membership, derived attention-queue, topic source, revision, update, and API response Pydantic contracts in `apps/api/app/agentic_research/contracts.py`, including the existing review API inputs (`run_id`, `source_url`, and `content_hash`) needed for an operator to resolve a visible review item.
- [X] T006 Add explicit bootstrap/migration SQL for `research_topics`, `research_topic_runs`, source provenance, wiki revision snapshot, contribution, exclusion, and update records in `apps/api/app/agentic_research/store.py` and `apps/api/app/database_bootstrap.py`.
- [X] T007 Extend `apps/api/app/agentic_research/store.py` with workspace-scoped topic creation/read methods, a deterministic derived attention-queue query, transactional topic-run attachment, topic row locking, and append-only revision persistence.
- [X] T008 Refactor the question-key handling in `apps/api/app/web_research/store.py` so normalized-question reuse is unique per `research_topic_runs.topic_id` rather than globally per workspace, while preserving the canonical `research_runs.status` lifecycle.
- [X] T009 [P] Add persistence and migration tests for topic isolation, normalized-name uniqueness, topic-scoped duplicate-question reuse, one-topic-per-run, and clean-start removal of standalone report artifacts in `apps/api/tests/test_agentic_research.py` and `apps/api/tests/test_database_bootstrap.py`.
- [X] T010 [P] Add contract tests for workspace isolation, malformed topic IDs, cross-workspace requests, topic/run conflicts, and an unresolved-review `409` response in `apps/api/tests/test_web_research.py`.
- [X] T011 Add a `TopicWorkspaceService` in `apps/api/app/agentic_research/topic_workspace.py` that coordinates validated topic/run creation through the existing `AgenticResearchStore` and `ResearchStore`, rechecks the derived attention queue transactionally, and does not own workflow status, trust, or capability decisions.
- [X] T012 Wire the topic service and typed dependencies in `apps/api/app/main.py` without adding a new worker, graph, or state machine.

**Checkpoint**: Topic identity, membership, and revisions have one PostgreSQL
owner; `research_runs.status` remains the single official workflow status.

---

## Phase 3: User Story 1 - Build Knowledge Under One Topic (Priority: P1) MVP

**Goal**: An operator can create/select a durable topic, ask questions within
it, and have the existing governed workflow contribute to that topic rather than
produce isolated work.

**Independent Test**: Create a topic, complete two different questions, and
verify both appear under the topic and their qualified evidence is associated
with that topic without duplicate question runs.

### Tests for User Story 1

- [X] T013 [P] [US1] Add unified-workflow integration tests for topic context propagation, RuntimeService/MCP authorization reuse, canonical run-status transitions, retry, stale checkpoint/Temporal continuation behavior, and existing review decision continuation in `apps/api/tests/test_unified_research_integration.py`.
- [X] T014 [P] [US1] Add graph-node tests proving blocked, review-required, malformed, or failed evidence cannot become a topic source or wiki input in `apps/api/tests/test_research_workflow_nodes.py`.
- [X] T015 [P] [US1] Add API tests for creating a topic, submitting/reusing a question under one topic versus independently under another, and this operator scenario: a visible review-required source blocks a follow-up question until accept or reject is recorded, after which the question can start in `apps/api/tests/test_web_research.py`.

### Implementation for User Story 1

- [X] T016 [US1] Add `POST /v1/research/topics`, `GET /v1/research/topics`, and `GET /v1/research/topics/{topic_id}` routes in `apps/api/app/main.py` with existing workspace authentication, typed error responses, and the derived attention queue.
- [X] T017 [US1] Add `POST /v1/research/topics/{topic_id}/questions` in `apps/api/app/main.py`; validate topic ownership, prevent a new question when the derived attention queue is non-empty, create/reuse a topic-scoped run only after it is clear, and call the existing `UnifiedResearchWorkflowEntry` only.
- [X] T018 [US1] Extend `apps/api/app/agent_runtime/research_workflow.py` and its typed state so a selected `topic_id` follows the current unified graph and no node may change topic membership or run status outside its current owner.
- [X] T019 [US1] Extend topic-aware graph bindings in `apps/api/app/agentic_research/workflow_nodes.py` so qualified evidence and completed summary artifacts are associated with the selected topic through `AgenticResearchStore`.
- [X] T020 [US1] Add deterministic topic-source association and introduction recording after existing trust, relevance, and summary checks in `apps/api/app/agentic_research/store.py`.
- [X] T021 [US1] Refactor the topic shell and topic-selection/question flow in `apps/web/src/App.tsx` so the ordinary action is choose/create a topic, resolve any visible **Needs your decision** item, ask a question, choose source count, and start the existing research flow.
- [X] T022 [US1] Add topic-workspace styles and responsive state handling in `apps/web/src/styles.css` so the derived attention queue is prominent and active, waiting-for-review, completed, failed, and reused-question states come from the stored run record.

**Checkpoint**: A topic has two independently visible governed research questions;
the UI never owns progress state or starts an alternate research path.

---

## Phase 4: User Story 2 - Read the Current Wiki and Latest Update (Priority: P1)

**Goal**: The topic has one current, grounded wiki with immutable revisions,
traceable citations, and a clear summary of the newest change.

**Independent Test**: Complete two qualifying questions in one topic, open the
current wiki, inspect the latest update and prior revision, and resolve each
citation to a stored summary and original URL.

### Tests for User Story 2

- [X] T023 [P] [US2] Add report-service tests for topic-wide qualified-summary snapshots, zero-or-one revision per run, no-change fingerprint outcomes, revision ordering, quality fallback, and citation validation in `apps/api/tests/test_agentic_research_reporting.py`.
- [X] T024 [P] [US2] Add integration tests for concurrent reporting, stale revision writers, report persistence failure, and rule that only a stored revision advances the current pointer in `apps/api/tests/test_unified_research_integration.py`.
- [X] T025 [P] [US2] Add API/UI-facing contract tests for current wiki, revision history, the stored **What changed since the previous revision** summary and link, unresolved citations, and no-qualified-evidence response states in `apps/api/tests/test_web_research.py`.

### Implementation for User Story 2

- [X] T026 [US2] Adapt `apps/api/app/agentic_research/reporting.py` so `ResearchReportingService` loads bounded topic-wide qualified summaries and builds a validated immutable wiki revision, revision inputs, contributions, exclusions, and latest update through its existing report boundary.
- [X] T027 [US2] Extend `apps/api/app/agentic_research/store.py` with deterministic fingerprint comparison, topic-row locking, next revision allocation, current-pointer publication, and no-change contribution recording.
- [X] T028 [US2] Adapt the existing final-report node in `apps/api/app/agentic_research/workflow_nodes.py` so it is the only caller that asks the reporting service to publish a topic revision after a completed topic run.
- [X] T029 [US2] Add topic wiki and revision-history read routes in `apps/api/app/main.py`, including current wiki, specific immutable revision, the stored change summary and prior-revision link, supporting stored-summary links, original URLs, exclusions, quality information, and explicit insufficient-evidence state.
- [X] T030 [US2] Replace the standalone report panel in `apps/web/src/App.tsx` with a Wiki view that renders stored Markdown, Latest update, **What changed since the previous revision**, revision history, source links, and quality/fallback explanations.
- [X] T031 [US2] Add wiki revision and citation navigation styling in `apps/web/src/App.css`, including visible but non-blocking report quality status and a readable no-evidence state.

**Checkpoint**: The graph has one reporting caller, the reporting service has one
topic-revision publication path, and a run without a changed qualified snapshot
does not create a duplicate wiki revision.

---

## Phase 5: User Story 3 - Inspect Research and the Source Library (Priority: P2)

**Goal**: The operator can inspect topic question history, retained sources,
summaries, keywords, trust outcomes, and accurate exclusion reasons.

**Independent Test**: A topic with usable and excluded sources shows their
question provenance, stored summary links, trust outcome, and concise reason.

### Tests for User Story 3

- [X] T032 [P] [US3] Add tests for topic Research and Sources read models, source reuse across questions, exclusion reason derivation, and review-required evidence exclusion in `apps/api/tests/test_agentic_research.py`.
- [X] T033 [P] [US3] Add API authorization tests for topic Research and Sources reads, workspace isolation, and exclusion-reason responses in `apps/api/tests/test_web_research.py`.

### Implementation for User Story 3

- [X] T034 [US3] Add topic Research and Sources read-model queries in `apps/api/app/agentic_research/store.py` that join canonical run, evidence, trust, summary, keyword, and provenance records without copying their authority.
- [X] T035 [US3] Add `GET /v1/research/topics/{topic_id}/research` and `GET /v1/research/topics/{topic_id}/sources` in `apps/api/app/main.py` with bounded pagination and workspace enforcement.
- [X] T036 [US3] Implement Research and Sources views, source-summary links, keyword display, introduction provenance, and exclusion labels in `apps/web/src/App.tsx`.
- [X] T037 [US3] Add dense, readable list and source-detail styling in `apps/web/src/App.css` with clear visual distinctions among used, excluded, review-required, and failed sources.

**Checkpoint**: Sources remain transparent and traceable; the only research
entry path in this release is an operator question within a selected topic.

---

## Phase 6: User Story 4 - Preserve a Clear Future Studio Boundary (Priority: P3)

**Goal**: Studio is visible as the future home for grounded outputs without
pretending those outputs can be generated today.

**Independent Test**: Open a topic workspace, select Studio, and confirm it is
read-only and contains no action that starts model work or artifact creation.

- [X] T038 [P] [US4] Add a UI behavior test or build-level assertion that Studio has no generation request or unavailable command in `apps/web/src/App.tsx` or its established frontend test location.
- [X] T039 [US4] Add the read-only Studio view and topic-grounded future-output description in `apps/web/src/App.tsx`.
- [X] T040 [US4] Add Studio placeholder styling in `apps/web/src/App.css` without controls that resemble enabled generation actions.

---

## Phase 7: Retirement, Documentation, and Verification

**Purpose**: Complete cutover without leaving duplicate product paths or stale
architecture records.

- [X] T041 Retire the standalone report read as the active UI/API path in `apps/api/app/main.py`, `apps/web/src/App.tsx`, and corresponding `apps/api/tests/test_research_report.py` coverage; preserve only explicitly approved temporary diagnostics.
- [X] T042 Remove obsolete standalone report persistence/callers and clean-start test fixtures in `apps/api/app/agentic_research/store.py`, `apps/api/app/agentic_research/reporting.py`, and `apps/api/tests/test_agentic_research_reporting.py`.
- [X] T043 [P] Update `docs/local-evidence-intelligence.md`, `docs/agent-runtime.md`, `docs/current-platform-architecture.md`, `docs/architecture-glossary.md`, `ROADMAP.md`, and ADR 0017 with the implemented paths and retired report behavior.
- [X] T044 Run API formatting/lint/tests from `apps/api`, frontend build from `apps/web`, database bootstrap/migration tests, and `git diff --check`; record results in the pull request.
- [ ] T045 Perform a manual local Docker verification using `specs/011-topic-research-wiki/quickstart.md`: create one topic, inspect and resolve a review-required evidence decision, confirm a second same-topic question is blocked until that decision, complete two questions, inspect revisions/citations/sources, submit a repeated question, and confirm Studio starts no work.

## Dependencies and Execution Order

1. Phase 1 must finish, including explicit operator approval at T004.
2. Phase 2 blocks all implementation stories.
3. US1 is the MVP and must establish the topic/run relationship before US2.
4. US2 requires US1 because revisions are published from topic-associated runs.
5. US3 requires the foundational records and reuses US1’s topic context; it may
   start after US1 while US2’s UI work is in progress.
6. US4 may start after US1’s topic shell exists.
7. Retirement starts only after all selected stories and migration tests pass.

## Parallel Opportunities

- T001-T003 can proceed together.
- T009 and T010 can proceed after the data model is settled.
- T013-T015 can proceed together after Phase 2.
- T023-T025 can proceed together after US1.
- T032-T033 can proceed together after the foundational phase.
- T038 can proceed alongside Studio implementation planning.
- T043 can proceed alongside final verification once concrete API names settle.

## Implementation Strategy

### MVP: User Story 1

Complete the durable topic record, topic-scoped question reuse, existing graph
context, and basic topic question UI. Validate that two questions remain under
one topic without changing the trust, RuntimeService, Temporal, or run-status
owners.

### Incremental Delivery

1. Deliver US1: a topic can contain governed questions.
2. Deliver US2: qualified results become versioned, traceable wiki revisions.
3. Deliver US3: research history and source library become inspectable.
4. Deliver US4: Studio boundary is visible, read-only, and honest.
5. Retire standalone reports only after topic workflow verification passes.

## Format Validation

All 45 tasks use the required checkbox, sequential task ID, optional parallel
marker, applicable user-story label, and concrete file path.
