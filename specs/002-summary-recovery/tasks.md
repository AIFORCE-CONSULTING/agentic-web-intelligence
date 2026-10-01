# Tasks: Reliable Summary Recovery

**Input**: Design documents from \`specs/002-summary-recovery/\`  
**Prerequisites**: \`plan.md\`, \`spec.md\`, \`research.md\`, \`data-model.md\`, \`contracts/summary-recovery.md\`, and \`quickstart.md\`

**Tests**: This changes durable, operator-visible workflow outcomes and stored records. Contract, store, direct-execution, Temporal, unified-workflow, and API tests are required. The operator completes the documented Research workspace review manually; the web application must still pass its production build.

**Organization**: Tasks are grouped by user story so each outcome can be implemented and reviewed independently. The existing \`EvidenceSummaryService\`, \`EvidenceSummaryStore\`, \`EvidenceSummaryAutomation\`, Temporal worker, unified LangGraph workflow, \`ResearchStore\`, \`AgenticResearchStore\`, and Research workspace remain the owners identified in the approved plan.

## Format: \`[ID] [P?] [Story] Description\`

- **[P]**: Can proceed in parallel because it changes separate files and has no dependency on unfinished work in the same phase.
- **[Story]**: Links a task to the user story it supports.
- Every task names its primary file path.

## Phase 1: Setup

**Purpose**: Establish the recovery contract and test fixtures without adding a new workflow, store, service, or source of status.

- [X] T001 Review the approved ownership matrix and retain its decisions in \`specs/002-summary-recovery/plan.md\` before editing runtime code.
- [ ] T002 [P] Add deterministic valid, malformed-JSON, and invalid-keyword provider fixtures in \`apps/api/tests/conftest.py\`.
- [X] T003 [P] Add summary-recovery contract test scaffolding in \`apps/api/tests/test_evidence_summary_recovery.py\`.
- [X] T004 [P] Add report-read API test scaffolding in \`apps/api/tests/test_research_report.py\`.

---

## Phase 2: Foundational Contract And Stored Attempt History

**Purpose**: Make v2 summary responses and their bounded recovery history durable before changing direct or Temporal execution.

**Checkpoint**: The model contract is simpler, each completed response has one safe diagnostic record, and idempotency rules prevent a third response for the same source-summary unit.

- [X] T005 Replace the v1 coverage-map Pydantic models, JSON schemas, prompts, and prompt version with the v2 chunk/consolidation \`summary\` and \`keywords\` contract and final-only \`evidence_sufficient\` field in \`apps/api/app/evidence_summaries/service.py\`.
- [X] T006 Add deterministic keyword uniqueness and count validation in \`apps/api/app/evidence_summaries/service.py\`. The original exact-phrase presence check is superseded by T044 because it rejected useful summaries for a formatting difference rather than a real contract failure.
- [X] T007 Extend summary API contracts with source attempt count, the shared safe failure-category vocabulary, and fixed operator-facing failure messages while retaining nullable historical coverage fields for reads in \`apps/api/app/evidence_summaries/contracts.py\`.
- [X] T008 Add the \`evidence_summary_attempts\` schema with cycle identity, reservation state, request deadline, per-source failure metadata, indexes, and a unique cycle/unit/attempt constraint to \`apps/api/app/evidence_summaries/store.py\`.
- [X] T009 Add transactional store methods that reserve one model-call slot before provider invocation, return existing reservations for duplicate delivery, and reject conflicting attempt or artifact writes in \`apps/api/app/evidence_summaries/store.py\`.
- [X] T010 Add guarded store transitions for accepted and rejected attempts, final-source completion including the `evidence_sufficient: false` outcome, terminal source failure, stale-reservation dependency failure, and execution completion when one or more sources are evidence-sufficient in \`apps/api/app/evidence_summaries/store.py\`.
- [ ] T011 [P] Add store tests for reservation uniqueness, duplicate delivery, stale reservation handling, accepted-result preservation, terminal source failure, illegal transitions, and partial execution completion in \`apps/api/tests/test_evidence_summary_store.py\`.
- [X] T012 [P] Add contract tests for v2 chunk versus final response shapes, JSON rejection, keyword count limits, and duplicate keywords in \`apps/api/tests/test_evidence_summary_recovery.py\`. Exact normalized phrase-presence assertions are superseded by T044.

---

## Phase 3: User Story 1 - Recover From One Invalid Model Response (Priority: P1) MVP

**Goal**: Give an eligible source one controlled corrective model response when the first completed response violates the v2 summary contract.

**Independent Test**: A deterministic model fixture returns invalid JSON or an invalid keyword list first and a valid replacement second. Exactly two completed responses are recorded for that unit, and only the valid response is stored as a summary.

### Tests for User Story 1

- [ ] T013 [P] [US1] Add direct-execution tests for invalid-first/valid-second chunk, consolidation, and final-source responses in \`apps/api/tests/test_evidence_summary_recovery.py\`.
- [X] T014 [P] [US1] Add a test proving the corrective prompt uses the same bounded evidence and includes only a safe validation category in \`apps/api/tests/test_evidence_summary_recovery.py\`.

### Implementation for User Story 1

- [X] T015 [US1] Add a typed completed-response validation result and safe corrective-instruction renderer in \`apps/api/app/evidence_summaries/service.py\`.
- [X] T016 [US1] Refactor model calls so each chunk, consolidation group, and final source summary first reserves attempt one, then makes at most one complete corrective replacement request after a rejected first response in \`apps/api/app/evidence_summaries/service.py\`.
- [X] T017 [US1] Record prompt version, model version, source version, unit identity, attempt number, accepted/rejected outcome, and safe validation detail through \`apps/api/app/evidence_summaries/store.py\`.
- [X] T018 [US1] Keep provider connection, HTTP, and Ollama dependency failures distinct from a completed invalid model response in \`apps/api/app/evidence_summaries/service.py\`.
- [ ] T019 [US1] Add direct-execution integration coverage that proves no invalid response becomes an artifact, keyword set, topic-coverage input, or report input in \`apps/api/tests/test_evidence_summary_recovery.py\`.

**Checkpoint**: One invalid completed response can recover without changing trust, authority, discovery, extraction, source reuse, or route selection.

---

## Phase 4: User Story 2 - Understand Why A Source Failed (Priority: P1)

**Goal**: Give the operator a clear, safe explanation when a source exhausts its one corrective response, without exposing raw model output or hidden instructions.

**Independent Test**: A fixture returns invalid output for both permitted responses. The source displays two attempts, typed failure category, prompt and model version, and a plain-language explanation, while the research status is still owned by the unified workflow.

### Tests for User Story 2

- [ ] T020 [P] [US2] Add tests for two invalid completed responses, safe diagnostic persistence, and no raw-response retention in \`apps/api/tests/test_evidence_summary_recovery.py\`.
- [ ] T021 [P] [US2] Add API tests for workspace-scoped source failure details, including `model_dependency_unavailable`, and separate dependency, extraction, trust, and workflow failure categories in \`apps/api/tests/test_evidence_summary_api.py\`.
- [ ] T022 [P] [US2] Add direct-versus-Temporal tests proving a worker restart or duplicate delivery cannot claim a third model-call slot, and that a stale reservation follows the dependency-failure path, in \`apps/api/tests/test_evidence_summary_workflow.py\`.

### Implementation for User Story 2

- [X] T023 [US2] Mark only the affected source terminally failed after its second rejected completed response and preserve any earlier accepted source artifact in \`apps/api/app/evidence_summaries/service.py\`.
- [X] T024 [US2] Return safe source attempt and failure fields from existing summary-execution reads, using the shared category vocabulary and fixed messages, in \`apps/api/app/evidence_summaries/store.py\` and \`apps/api/app/evidence_summaries/contracts.py\`.
- [X] T025 [US2] Update the existing summary automation and Temporal activity so source-level exhaustion and dependency failures return the stored partial or failed execution outcome with their owner-written category rather than failing the entire worker on the first source error in \`apps/api/app/evidence_summaries/workflow.py\`.
- [X] T026 [US2] Preserve the unified LangGraph research record as the sole operator-facing status writer when summary execution returns its stored outcome in \`apps/api/app/agentic_research/workflow_nodes.py\`.
- [X] T027 [US2] Show the existing Research workspace's source summary status, attempt count, category message, and safe failure reason without adding a workflow trigger in \`apps/web/src/App.tsx\`.

**Checkpoint**: Operators can distinguish a model-format failure from an extraction, trust, dependency, or workflow problem without reading worker logs.

---

## Phase 5: User Story 3 - Preserve Useful Research When One Source Fails (Priority: P2)

**Goal**: Continue topic coverage and reporting from valid stored source summaries while transparently identifying sources omitted after summary recovery was exhausted.

**Independent Test**: Two eligible, relevant sources run together; one obtains a valid summary and one exhausts recovery. The research task completes from the valid source only, coverage and the report exclude the failed source, and the stored report contains a platform-generated omission notice.

### Tests for User Story 3

- [ ] T028 [P] [US3] Add unified-workflow integration tests for partial success, all-source exhaustion, an `evidence_sufficient: false` source, qualified coverage, and report grounding in \`apps/api/tests/test_unified_research_workflow.py\`.
- [ ] T029 [P] [US3] Add reporting-service tests that accept only qualified artifacts and append trusted omitted-source disclosure outside the model prompt in \`apps/api/tests/test_research_reporting.py\`.
- [ ] T030 [P] [US3] Add authenticated report-read API tests for absent, complete, and partial research reports in \`apps/api/tests/test_research_report.py\`.
- [X] T031 [P] [US3] Document manual Research workspace review for a read-only final report, omitted-source notice, and all-source-failure absence state in \`specs/002-summary-recovery/quickstart.md\`.

### Implementation for User Story 3

- [X] T032 [US3] Update execution completion and summary automation to continue only when at least one accepted source artifact has \`evidence_sufficient: true\` and fail when none exists in \`apps/api/app/evidence_summaries/service.py\` and \`apps/api/app/evidence_summaries/workflow.py\`.
- [X] T033 [US3] Compose and store a deterministic omitted-source notice from safe failed or insufficient source outcomes while continuing to pass only qualified, evidence-sufficient artifacts to the report model in \`apps/api/app/agentic_research/reporting.py\`.
- [X] T034 [US3] Add the authenticated, workspace-scoped, read-only \`GET /v1/research/runs/{run_id}/report\` endpoint in \`apps/api/app/main.py\`.
- [X] T035 [US3] Load and render the stored final report after the existing Keywords section, including the platform-generated omission notice, in \`apps/web/src/App.tsx\`.
- [ ] T036 [US3] Add an end-to-end direct and Temporal-backed scenario proving blocked and review-required evidence remains outside summary and report inputs in \`apps/api/tests/test_unified_research_workflow.py\`.

**Checkpoint**: A report is available only when qualified summaries exist. It never treats a failed, blocked, or review-required source as support.

---

## Phase 6: Documentation, Compatibility, And Full Verification

**Purpose**: Document the simplified v2 contract, maintain historical read compatibility, and prove all recovery paths behave consistently.

- [X] T037 [P] Amend summary-contract, schema, prompt-version, and recovery language in \`docs/adr/0014-governed-local-model-provider.md\`.
- [X] T038 [P] Update recovery behavior, operator-visible outcomes, and final-report disclosure in \`docs/local-evidence-intelligence.md\`.
- [X] T039 [P] Update the feature verification procedures and expected results in \`specs/002-summary-recovery/quickstart.md\`.
- [ ] T040 Add historical v1 artifact read and source-reuse compatibility tests in \`apps/api/tests/test_evidence_summary_store.py\`.
- [X] T041 Run API lint and the focused recovery, store, Temporal, unified-workflow, reporting, and API test suite from \`apps/api/\`.
- [X] T042 Run the web production build from \`apps/web/\`.
- [ ] T043 Run the documentation build, Compose verification, and the complete \`quickstart.md\` scenario set from repository root.

---

## Phase 7: One Coherent Summary Stage

**Purpose**: Correct the live failure discovered during a fresh research run:
the platform must not reject a useful summary solely because a keyword phrase
is not repeated word-for-word, and it must treat all internal five-source
summary jobs for one research task as one complete stage before the graph
continues.

- [ ] T044 Update summary prompts, JSON validation, safe corrective feedback, and tests so that the contract requires valid JSON, the required fields, nonblank unique keywords, and the configured keyword count only. Keep keyword-to-summary alignment as a prompt instruction rather than a literal phrase-presence rejection in \`apps/api/app/evidence_summaries/service.py\` and \`apps/api/tests/test_evidence_summary_recovery.py\`.
- [ ] T045 Add the canonical summary work-set and work-set-member schema, guarded transitions, aggregate read model, and concurrency tests in \`apps/api/app/evidence_summaries/store.py\` and \`apps/api/tests/test_evidence_summary_store.py\`.
- [ ] T046 Retire the candidate-preflight worker's automatic summary launch. Preflight must persist its retrieval and trust outcome and resume the unified LangGraph workflow only in \`apps/api/app/durable_execution/worker.py\` and its tests.
- [ ] T047 Add one summary-stage entry point used by the unified graph after relevance. It creates one work set, plans fixed internal jobs of at most five relevant sources, routes each through the existing direct-or-Temporal summary mechanism, and attaches every job to the work set in \`apps/api/app/evidence_summaries/workflow.py\` and \`apps/api/app/evidence_summaries/service.py\`.
- [ ] T048 Change direct and Temporal completion handling so an internal execution updates its work set. Resume the graph exactly once only after all member jobs are terminal; permit partial success and fail the research task only when the aggregate has no usable summaries or state conflicts in \`apps/api/app/durable_execution/worker.py\` and \`apps/api/app/agentic_research/workflow_nodes.py\`.
- [ ] T049 Update the unified LangGraph summary node and guarded research-status transitions so \`research_runs.status\` remains the only operator-facing workflow status, and the graph proceeds to coverage and reporting only from a completed aggregate work set in \`apps/api/app/agentic_research/workflow_nodes.py\`.
- [ ] T050 Replace the Research workspace's latest-execution summary display with the combined work-set read model and source failure details in \`apps/api/app/main.py\`, \`apps/web/src/App.tsx\`, and their API/UI tests.
- [ ] T051 Add direct and Temporal-backed integration coverage for more than five relevant sources, partial member failure, all-member failure, duplicate delivery, one graph resumption, and report grounding from only successful eligible relevant summaries in \`apps/api/tests/test_unified_research_workflow.py\`.
- [ ] T052 Amend ADR 0014, ADR 0016, local evidence documentation, quickstart verification, and this feature's data model and contracts to describe the unified summary-stage ownership and simplified keyword contract.

---

## Dependencies And Execution Order

### Phase Dependencies

- **Phase 1** has no runtime dependencies.
- **Phase 2** supplies the contract and canonical diagnostics required by every story.
- **User Story 1** depends on Phase 2.
- **User Story 2** depends on User Story 1 because it uses its attempt records and corrective validation result.
- **User Story 3** depends on User Story 2 because partial completion and omitted-source reporting require terminal source outcomes.
- **Phase 6** follows the implemented stories.

### User Story Completion Order

\`\`\`text
Setup -> Foundational -> US1 recovery -> US2 explanation -> US3 partial report -> verification
\`\`\`

### Parallel Opportunities

- T002--T004 can proceed in parallel after the existing test patterns are read.
- T011 and T012 can proceed in parallel once T005--T010 establish the contract and store API.
- Each test group marked \`[P]\` in T013--T014, T020--T022, and T028--T031 can proceed in parallel after its story's interface is stable.
- T037--T039 can proceed in parallel after the final behavior is established.

## Implementation Strategy

### MVP First

1. Complete Phases 1 and 2.
2. Complete User Story 1 and its direct-execution tests.
3. Validate that one malformed response is corrected exactly once and never accepted before correction.

### Incremental Delivery

1. Add source-level diagnostics and direct/Temporal consistency through User Story 2.
2. Add partial-result reporting and the read-only report view through User Story 3.
3. Finish documentation, historical-read compatibility, and full Compose verification.

## Notes

- These tasks implement the approved plan; they do not grant new authority to the model, alter RuntimeService, or change web-trust policy behavior.
- \`keyword_coverage\` is retained only as nullable historical read data. New v2 work neither requests nor writes it.
- No task introduces a second research status, orchestration path, durable execution mechanism, source of truth, or operator start action.
