# Tasks: Human Evidence Review Rejection

**Input**: Design documents from `/specs/006-review-reject/`
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/review-reject-api.md](./contracts/review-reject-api.md)

**Tests**: Required. This feature changes a human approval boundary, workflow continuation, API behavior, persisted review decisions, and operator UI.

**Organization**: Tasks are grouped by user story so each story can be implemented and tested independently.

## Phase 1: Setup

**Purpose**: Confirm the active feature context and preserve the approved design boundary before implementation begins.

- [X] T001 Confirm `.specify/feature.json` points to `specs/006-review-reject` and that `AGENTS.md` references `specs/006-review-reject/plan.md`
- [X] T002 Review the approved architecture ownership matrix in `specs/006-review-reject/plan.md` before editing runtime or UI code
- [X] T003 [P] Review the API contract in `specs/006-review-reject/contracts/review-reject-api.md` against the existing accept endpoint in `apps/api/app/main.py`

---

## Phase 2: Foundational

**Purpose**: Shared contract and persistence groundwork needed by all user stories.

**Critical**: Runtime code work must not begin until the design checkpoint in the plan has explicit user approval.

- [X] T004 Add typed human review outcome fields and request models to `apps/api/app/web_trust/contracts.py`
- [X] T005 Add `outcome` persistence support to `web_evidence_trust_overrides` in `apps/api/app/web_trust/store.py`, treating existing rows as `accepted`
- [X] T006 Update `WebTrustStore.latest_evaluation` and `WebTrustStore.list_latest_evaluations` in `apps/api/app/web_trust/store.py` so only active `accepted` decisions make effective disposition `eligible`
- [X] T007 Update existing acceptance behavior in `apps/api/app/web_trust/service.py` to use the explicit `accepted` outcome without changing the public accept contract

**Checkpoint**: Shared review-decision data can represent both `accepted` and `rejected`, while old acceptance rows remain readable.

---

## Phase 3: User Story 1 - Reject Review-Required Evidence (Priority: P1) MVP

**Goal**: Let an authenticated operator reject one exact review-required evidence version, keep it stored for audit, resume the same workflow, and continue without using that source in automated model context.

**Independent Test**: Start a run with review-required evidence, reject it from the review panel without entering a reason, and confirm the same run continues without summarizing or reporting that rejected source.

### Tests for User Story 1

- [X] T008 [P] [US1] Add failing store/service tests for recording a rejected review-required evidence decision in `apps/api/tests/test_web_trust.py`
- [X] T009 [P] [US1] Add failing API contract tests for `POST /v1/research/runs/{run_id}/evidence-trust/reject` in `apps/api/tests/test_web_trust.py`
- [X] T010 [P] [US1] Add failing unified workflow test proving rejection resumes the same paused run and excludes the rejected source in `apps/api/tests/test_unified_research_workflow.py`
- [X] T011 [P] [US1] Add failing test proving rejected evidence, trust evaluation, retrieval facts, reviewer identity, timestamp, and optional reviewer note remain visible after rejection in `apps/api/tests/test_web_trust.py`
- [X] T012 [P] [US1] Add failing workflow test with multiple review-required sources proving rejecting one source does not silently approve, delete, or skip unresolved review decisions in `apps/api/tests/test_unified_research_workflow.py`

### Implementation for User Story 1

- [X] T013 [US1] Implement `WebTrustStore.reject_evaluation` in `apps/api/app/web_trust/store.py`
- [X] T014 [US1] Implement `EvidenceTrustService.reject` in `apps/api/app/web_trust/service.py`
- [X] T015 [US1] Generalize `EvidenceTrustService.record_workflow_resume` and `WebTrustStore.record_workflow_resume` in `apps/api/app/web_trust/service.py` and `apps/api/app/web_trust/store.py` so they accept either stored `accepted` or stored `rejected` decisions
- [X] T016 [US1] Add `POST /v1/research/runs/{run_id}/evidence-trust/reject` to `apps/api/app/main.py`
- [X] T017 [US1] Update `UnifiedResearchWorkflowEntry.resume_after_review` in `apps/api/app/agent_runtime/research_workflow.py` to resume with `accepted` or `rejected` outcomes after loading the stored human decision
- [X] T018 [US1] Update the review interrupt handling in `apps/api/app/agent_runtime/research_workflow.py` so a rejected source stays excluded while the graph continues with remaining usable evidence
- [X] T019 [US1] Update candidate/relevance filtering in `apps/api/app/agentic_research/workflow_nodes.py` so rejected review-required evidence is not considered eligible for relevance, summaries, topic coverage, or reporting
- [X] T020 [US1] Add a Reject evidence action, confirmation copy, and reject submission handler to `apps/web/src/App.tsx`
- [X] T021 [US1] Update review panel styling for dual Accept/Reject actions in `apps/web/src/styles.css`

**Checkpoint**: User Story 1 is independently functional and testable.

---

## Phase 4: User Story 2 - Pause Correctly for Review During Relevance (Priority: P2)

**Goal**: Permit the official research status to move from relevance evaluation into human review when review-required evidence appears at that point in the workflow.

**Independent Test**: Run a workflow scenario where relevance evaluation encounters review-required evidence and confirm the operator-visible run status becomes `awaiting_review`.

### Tests for User Story 2

- [X] T022 [P] [US2] Add failing transition-table test for `evaluating_relevance -> awaiting_review` in `apps/api/tests/test_web_research.py`
- [X] T023 [P] [US2] Add failing workflow test proving relevance-stage review-required evidence transitions to `awaiting_review` in `apps/api/tests/test_unified_research_workflow.py`

### Implementation for User Story 2

- [X] T024 [US2] Add `awaiting_review` to the `evaluating_relevance` transition set in `apps/api/app/web_research/store.py`
- [X] T025 [US2] Update the unified workflow status mapping in `apps/api/app/agent_runtime/research_workflow.py` so relevance-stage review pauses write `awaiting_review`
- [X] T026 [US2] Verify the UI status text in `apps/web/src/App.tsx` clearly displays `awaiting_review` instead of implying relevance is still processing

**Checkpoint**: User Stories 1 and 2 both work independently.

---

## Phase 5: User Story 3 - Prevent Unsafe or Ambiguous Review Decisions (Priority: P3)

**Goal**: Keep human review decisions explicit, version-scoped, auditable, and inaccessible to models, agents, stale UI actions, and invalid source states.

**Independent Test**: Attempt invalid review actions and confirm the platform refuses them with clear errors while recording no unauthorized review decision.

### Tests for User Story 3

- [X] T027 [P] [US3] Add failing tests proving rejection succeeds without a reason while preserving any optional note when provided in `apps/api/tests/test_web_trust.py`
- [X] T028 [P] [US3] Add failing tests for rejecting eligible, blocked, or already-decided evidence in `apps/api/tests/test_web_trust.py`
- [X] T029 [P] [US3] Add failing tests that unauthenticated or non-human callers cannot accept or reject evidence in `apps/api/tests/test_web_trust.py`
- [X] T030 [P] [US3] Add failing retry/idempotency test for resume failure after rejection is recorded in `apps/api/tests/test_unified_research_workflow.py`

### Implementation for User Story 3

- [X] T031 [US3] Enforce review-required-only rejection decisions while allowing empty rejection reasons in `apps/api/app/web_trust/service.py`
- [X] T032 [US3] Enforce first-effective-decision-wins conflict handling in `apps/api/app/web_trust/store.py`
- [X] T033 [US3] Return clear conflict and validation responses for invalid accept/reject attempts in `apps/api/app/main.py`
- [X] T034 [US3] Ensure stale or conflicting graph resume attempts reload the stored decision and fail safely in `apps/api/app/agent_runtime/research_workflow.py`
- [X] T035 [US3] Update the UI review panel in `apps/web/src/App.tsx` so Reject does not require a reason and still surfaces server conflict messages

**Checkpoint**: All user stories are independently functional and tested.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, ADR alignment, and verification across the complete feature.

- [X] T036 [P] Update local evidence review documentation in `docs/local-evidence-intelligence.md`
- [X] T037 [P] Update ADR 0015 wording for accepted and rejected review-required evidence in `docs/adr/0015-local-policy-controlled-web-trust.md`
- [X] T038 [P] Update ADR 0016 wording for human review outcomes and graph continuation in `docs/adr/0016-governed-local-agent-capability-requests.md`
- [X] T039 [P] Update the feature quickstart if implementation details changed in `specs/006-review-reject/quickstart.md`
- [X] T040 Run API lint and targeted tests for web trust, research transitions, and unified workflow from `apps/api`
- [X] T041 Run frontend build or test command for the updated review panel in `apps/web`
- [X] T042 Run `git diff --check` from the repository root

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup and blocks all user stories.
- **User Story 1 (Phase 3)**: Depends on Foundational and is the MVP.
- **User Story 2 (Phase 4)**: Depends on Foundational; can be implemented after or alongside US1, but full review continuation is easier to verify after US1.
- **User Story 3 (Phase 5)**: Depends on Foundational and should run after US1 establishes the reject path.
- **Polish (Phase 6)**: Depends on completed implementation stories.

### User Story Dependencies

- **US1**: Primary MVP. Delivers the reject action and workflow continuation.
- **US2**: Independent transition fix, but benefits from US1 for end-to-end review testing.
- **US3**: Hardens the same boundary after US1 creates the rejection path.

### Parallel Opportunities

- T003 can run in parallel with T001-T002.
- T008-T012 can be written in parallel because they cover different test files or concerns.
- T022-T023 can be written in parallel.
- T027-T030 can be written in parallel.
- T036-T039 can be completed in parallel after implementation decisions settle.

## Parallel Example: User Story 1

```text
Task: "Add failing store/service tests for recording a rejected review-required evidence decision in apps/api/tests/test_web_trust.py"
Task: "Add failing API contract tests for POST /v1/research/runs/{run_id}/evidence-trust/reject in apps/api/tests/test_web_trust.py"
Task: "Add failing unified workflow test proving rejection resumes the same paused run and excludes the rejected source in apps/api/tests/test_unified_research_workflow.py"
```

## Implementation Strategy

### MVP First

1. Complete Phase 1 and Phase 2.
2. Complete Phase 3 for User Story 1.
3. Run the US1 tests and manually verify reject from the UI.
4. Stop for review before expanding into US2 and US3 if the workflow behavior looks different than expected.

### Incremental Delivery

1. Add explicit human review outcomes without changing accept behavior.
2. Add rejection and same-run continuation.
3. Add the missing relevance-to-review transition.
4. Add invalid-decision and retry/idempotency protections.
5. Update docs and run full verification.

### Notes

- `[P]` means the task can run in parallel with other marked tasks when no file conflict exists.
- Each story includes failing tests before implementation.
- Do not add another review workflow, policy authority, research start path, MCP capability, or Temporal workflow.
- Commit after each coherent implementation slice.
