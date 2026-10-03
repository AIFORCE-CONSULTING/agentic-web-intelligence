# Feature Specification: Completed Checkpoint Cleanup

**Feature Branch**: `005-checkpoint-cleanup`  
**Created**: 2026-10-02  
**Status**: Draft  
**Input**: User description: "Improve completed LangGraph checkpoint cleanup for the unified research workflow so completed-run checkpoint maintenance does not block unrelated new research runs."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Start New Research After Completion (Priority: P1)

As an operator, I want to start a new research search after a prior search completed without being blocked by leftover workflow cleanup work, so testing and normal research can continue smoothly.

**Why this priority**: The current behavior stops the operator with a maintenance message after a completed run. That makes a successful run look like a system problem and prevents the next research task.

**Independent Test**: Complete one research run, leave its completed execution bookmarks pending cleanup, then start a different research question. The new research request should be accepted without requiring manual cleanup first.

**Acceptance Scenarios**:

1. **Given** a completed research run has pending execution-bookmark cleanup, **When** the operator starts a different research question, **Then** the new research run starts or resumes normally.
2. **Given** a completed research run has pending execution-bookmark cleanup, **When** the operator views system health, **Then** cleanup is shown as maintenance backlog instead of a hard blocker for new research.

---

### User Story 2 - Preserve Completed Research Results (Priority: P2)

As an operator, I want cleanup to remove only completed-run execution bookmarks, so completed evidence, summaries, keywords, trust decisions, audit history, and final reports remain available.

**Why this priority**: Cleanup must be safe. The operator should never worry that maintenance cleanup deletes research outputs or weakens auditability.

**Independent Test**: Complete a research run, run cleanup for that completed run, and confirm the research record, source summaries, trust records, keywords, final report, and audit records remain readable.

**Acceptance Scenarios**:

1. **Given** a completed research run with stored evidence and a final report, **When** cleanup succeeds, **Then** the completed research data remains visible and unchanged.
2. **Given** cleanup is attempted for a completed research run, **When** cleanup completes, **Then** an audit record states whether cleanup succeeded or failed.

---

### User Story 3 - Recover From Cleanup Failure (Priority: P3)

As an operator, I want cleanup failures to be recorded and retryable without changing the completed status of the research run, so maintenance issues do not corrupt business state.

**Why this priority**: Cleanup is operational housekeeping. A failed cleanup should be visible and recoverable, but it should not undo the completed research outcome.

**Independent Test**: Simulate cleanup failure for a completed research run. The run stays completed, the failure is recorded, a new unrelated research run can start, and the existing maintenance command can retry cleanup later.

**Acceptance Scenarios**:

1. **Given** a completed research run, **When** cleanup fails, **Then** the run remains completed and a failed cleanup audit record is stored.
2. **Given** a prior cleanup failure, **When** the retry maintenance action succeeds later, **Then** a succeeded cleanup audit record is stored and the cleanup backlog is reduced.

### Edge Cases

- Cleanup is requested for a research run that is still active, waiting, failed, or awaiting review.
- Cleanup succeeds but no execution bookmarks exist for the completed run.
- Cleanup fails because checkpoint persistence is temporarily unavailable.
- Multiple cleanup attempts are made for the same completed run.
- A new research request arrives while cleanup for a previous completed run is still pending.
- Startup retry finds old completed runs with failed or missing cleanup audit records.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST treat completed-run execution-bookmark cleanup as maintenance work, not as a prerequisite for starting unrelated new research.
- **FR-002**: When a research run reaches the completed state, the system MUST attempt best-effort cleanup for that run's execution bookmarks.
- **FR-003**: Cleanup MUST remove only resumable workflow bookmark data for completed runs.
- **FR-004**: Cleanup MUST NOT delete or alter research questions, discovered sources, evidence, summaries, keywords, trust decisions, relevance decisions, final reports, or audit history.
- **FR-005**: Every cleanup attempt MUST record a durable audit outcome of succeeded or failed.
- **FR-006**: If cleanup fails, the completed research run MUST remain completed.
- **FR-007**: If cleanup fails, operators MUST still be able to start a new unrelated research run.
- **FR-008**: The system MUST keep a bounded retry path for pending or failed completed-run cleanup.
- **FR-009**: System health MAY report pending cleanup as degraded maintenance, but MUST NOT present it as a hard blocker for new unrelated research.
- **FR-010**: Operator-visible cleanup messages MUST explain that cleanup affects execution bookmarks only and does not delete completed research outputs.
- **FR-011**: Cleanup MUST be safe to retry without creating duplicate business results or changing completed research state.
- **FR-012**: Cleanup MUST use the platform-approved framework deletion mechanism rather than direct table deletion.

### Authority and Safety Boundaries *(include for agent, workflow, or external-action features)*

- **Authorized actors**: The platform may automatically attempt completed-run cleanup after a research run reaches completed status. An authenticated operator may trigger the existing bounded maintenance retry.
- **Human-only decisions**: No human research acceptance, override, or trust-policy decision is made by cleanup.
- **Agent limitations**: The model and agent workflow cannot request cleanup, decide cleanup success, mark evidence trusted, or change research completion status.
- **Canonical record**: The official research run status remains the operator-facing workflow state. Cleanup audit records state only whether execution-bookmark cleanup succeeded or failed.
- **Operator-visible states**: A completed research run stays completed whether cleanup succeeds or fails. Cleanup backlog is maintenance health, not research status.
- **Decision authority**: Platform workflow rules decide when cleanup is eligible. The approved checkpoint lifecycle component performs cleanup. The research store records the audit outcome.
- **Conflict outcome**: If cleanup records and execution bookmarks disagree, completed research data remains authoritative. The system retries cleanup through the bounded maintenance path and reports maintenance backlog without blocking unrelated new research.
- **Excluded behavior**: This feature does not add a new research workflow, does not change trust-policy rules, does not delete research outputs, does not add a new operator start button, and does not introduce a second source of workflow state.

### Key Entities *(include if feature involves data)*

- **Execution Bookmark**: Temporary resumable workflow state used while a research run is active or waiting for background work. It is not a research result.
- **Completed Research Run**: A research task whose official operator-facing status is completed and whose research outputs must remain available.
- **Cleanup Audit Record**: A durable record that says whether execution-bookmark cleanup for a completed research run succeeded or failed, including any safe explanation.
- **Cleanup Backlog**: Completed research runs that do not yet have a successful cleanup audit record.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After a research run completes, an operator can start a different research question without manual checkpoint cleanup in 100% of tested cases.
- **SC-002**: Cleanup success removes completed-run execution bookmarks while preserving 100% of completed research outputs and audit records.
- **SC-003**: Cleanup failure leaves the completed research run completed in 100% of tested failure cases.
- **SC-004**: Cleanup failures are visible through durable audit records in 100% of tested failure cases.
- **SC-005**: The bounded maintenance retry reduces pending cleanup backlog after the underlying cleanup dependency becomes available.

## Assumptions

- The platform will continue using the existing unified research workflow and existing cleanup audit table.
- Completed research outputs are stored separately from execution bookmarks and should be retained after cleanup.
- Cleanup is best-effort maintenance and should be retryable rather than part of research quality grading.
- Active, waiting, failed, or review-required research runs may still need execution bookmarks for safe continuation and are outside completed-run cleanup.
