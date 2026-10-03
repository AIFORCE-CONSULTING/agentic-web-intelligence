# Feature Specification: Human Evidence Review Rejection

**Feature Branch**: `006-review-reject`  
**Created**: 2026-10-03  
**Status**: Draft  
**Input**: User description: "Add an operator-facing reject action for review-required evidence. Today review-required evidence can be inspected and accepted, but not rejected. Rejecting should record that the human reviewed this exact evidence version and does not allow it into automated model context, keep the evidence and trust records, resume the same workflow, and continue without that source. Also fix the missing evaluating_relevance to awaiting_review status transition so review-required evidence can pause the workflow correctly."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Reject Review-Required Evidence (Priority: P1)

As an operator reviewing a source that requires human review, I want to reject
that exact evidence version so the research workflow can continue without using
it in automated model context.

**Why this priority**: The current review experience only lets the operator
accept evidence. If the operator decides the source should not be used, the
research run can remain waiting with no clear way forward.

**Independent Test**: Start a research run that encounters review-required
evidence, open the human review panel, reject the evidence, and confirm the run
continues without that source being summarized or used in the final report.

**Acceptance Scenarios**:

1. **Given** a research run is waiting for human review of a specific evidence version, **When** the operator rejects that evidence, **Then** the rejection is recorded and the workflow resumes without allowing that evidence into automated model context.
2. **Given** rejected review-required evidence remains stored, **When** the operator views the source later, **Then** the source, trust evaluation, reviewer identity, timestamp, and optional reviewer note remain visible for audit and explanation.
3. **Given** rejected evidence belongs to one source among several, **When** the workflow resumes, **Then** other eligible or accepted sources continue through relevance, summarization, and reporting.

---

### User Story 2 - Pause Correctly for Review During Relevance (Priority: P2)

As an operator, I want the workflow to enter the review state whenever
review-required evidence is discovered during relevance evaluation, so the run
does not become stuck in an internal processing state.

**Why this priority**: The workflow already understands that some evidence needs
human review, but the official status rules currently reject the transition from
relevance evaluation into the review state.

**Independent Test**: Run research where review-required evidence is detected
during relevance evaluation and confirm the operator-visible status becomes
waiting for review rather than remaining in relevance evaluation.

**Acceptance Scenarios**:

1. **Given** a source requires human review during relevance evaluation, **When** the workflow tries to pause for review, **Then** the research run enters the operator-visible review state.
2. **Given** a run is in the review state, **When** the operator accepts or rejects the exact evidence version, **Then** the workflow resumes from the same research task instead of starting a second workflow.

---

### User Story 3 - Prevent Unsafe or Ambiguous Review Decisions (Priority: P3)

As an operator and platform owner, I want review decisions to be explicit,
auditable, and limited to the exact evidence version reviewed, so neither a
model nor a stale UI action can approve or reject the wrong source.

**Why this priority**: Human review is a trust boundary. A rejection must not be
treated as deletion, and an acceptance must not be generalized to a different
source or content version.

**Independent Test**: Attempt to reject evidence that is not review-required or
an evidence version that no longer matches the run, and confirm the platform
refuses the decision with a clear explanation.

**Acceptance Scenarios**:

1. **Given** a source is eligible, blocked, or already decided, **When** the operator attempts to reject it through the review action, **Then** the platform refuses because only review-required evidence can be reviewed.
2. **Given** the operator submits a rejection without an explanation, **When** the decision is processed, **Then** the platform records the rejection because an explanation is optional in this first version.
3. **Given** an agent or model output attempts to accept or reject evidence, **When** the workflow evaluates that request, **Then** the request is ignored or denied because only an authenticated human operator may make the decision.

---

### Edge Cases

- The operator rejects one review-required source while other review-required
  sources remain. The workflow should continue only when the current waiting
  review condition has been resolved according to the workflow state.
- The operator tries to reject evidence after another operator already accepted
  or rejected the same exact evidence version. The platform should preserve the
  first effective decision or return a clear conflict response rather than
  silently replacing it.
- The workflow resume step fails after the rejection is recorded. The rejection
  remains durable, and retrying the workflow should reuse the recorded decision
  instead of asking the operator to decide again.
- Rejected evidence must remain visible and auditable, but must not appear in
  automated model context, generated summaries, keyword cards, topic coverage,
  or final reports.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST allow an authenticated operator to reject an exact `review_required` evidence version after inspecting it.
- **FR-002**: A rejection MUST record the human identity, source URL, content hash, timestamp, workspace, research run, reviewed trust evaluation, and any optional reviewer note the operator provides.
- **FR-003**: Rejected evidence MUST remain stored and visible for audit; rejection MUST NOT delete the source, evidence, trust evaluation, or retrieval facts.
- **FR-004**: Rejected evidence MUST remain excluded from automated model context, summaries, keyword extraction, topic coverage, and final report generation.
- **FR-005**: The system MUST resume the same waiting research workflow after a rejection so remaining eligible or accepted evidence can continue.
- **FR-006**: The system MUST keep existing acceptance behavior unchanged: accepted review-required evidence becomes eligible for automated use only for the exact accepted evidence version.
- **FR-007**: The system MUST reject review decisions for evidence that is not currently `review_required`.
- **FR-008**: The system MUST allow rejection without requiring a human-provided reason in this first version. If the operator provides a note, the system MUST preserve it with the review decision.
- **FR-009**: The system MUST prevent models, agents, background workers, and unauthenticated callers from accepting or rejecting evidence.
- **FR-010**: The system MUST allow the research workflow to transition from relevance evaluation into the review state when review-required evidence is encountered there.
- **FR-011**: The UI MUST offer both Accept and Reject actions in the human review panel with clear confirmation language explaining the consequence of each action.
- **FR-012**: The operator-facing run status MUST make clear when research is waiting for human review rather than still processing relevance.
- **FR-013**: A rejection MUST be safe to retry after a resume failure without creating duplicate business outcomes or allowing rejected evidence into model context.

### Authority and Safety Boundaries *(include for agent, workflow, or external-action features)*

- **Authorized actors**: Only an authenticated human operator with research write authority may accept or reject review-required evidence.
- **Human-only decisions**: Accepting or rejecting review-required evidence is always a human decision. A model, agent, workflow node, MCP tool, or background worker must never manufacture this decision.
- **Agent limitations**: Agents may observe that evidence is waiting for review, but they cannot approve it, reject it, alter the reason, or bypass the recorded decision.
- **Canonical record**: The durable human review decision for the exact evidence version is the business record that controls whether review-required evidence may enter automated model context.
- **Operator-visible states**: `awaiting_review` means the research task is paused for an operator decision about one or more exact evidence versions. Rejected means the reviewed evidence stays excluded while the workflow may continue with other usable evidence.
- **Decision authority**: Trust policy decides that evidence requires review; the human operator decides accept or reject; workflow code resumes the same research task after a recorded decision.
- **Conflict outcome**: If the stored review decision and workflow checkpoint disagree, the stored human decision wins. The workflow must reload the stored decision and continue safely or report a retryable conflict.
- **Excluded behavior**: This feature does not add policy editing, bulk approval, automatic rejection by model, deletion of rejected evidence, a second review workflow, or a new research start button.

### Key Entities *(include if feature involves data)*

- **Review-Required Evidence Version**: A captured source version identified by source URL and content hash that the trust policy preserves but excludes from automated use until a human decision exists.
- **Human Review Decision**: A durable operator decision for one exact evidence version. The decision is either accepted or rejected and includes the actor, timestamp, scope, related trust evaluation, and optional reviewer note.
- **Research Review State**: The operator-visible waiting state for a research run that cannot continue until the required human decision is recorded.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In 100% of tested review-required cases, the operator can choose either Accept or Reject from the review panel.
- **SC-002**: In 100% of tested rejection cases, rejected evidence remains visible for audit but is absent from summaries, keyword cards, topic coverage, and final reports.
- **SC-003**: In 100% of tested rejection cases with other usable evidence, the workflow resumes and continues without requiring a new research run.
- **SC-004**: In 100% of tested relevance-stage review cases, the run enters the review state instead of remaining stuck in relevance evaluation.
- **SC-005**: In 100% of tested invalid review attempts, the platform refuses the action with a clear explanation and records no unauthorized review decision.

## Assumptions

- Existing authentication and workspace permission checks remain the authority
  gate for operator review actions.
- Rejection is scoped to the exact source URL and content hash reviewed by the
  operator; it does not create a domain-wide or future-run block rule.
- Rejected evidence remains useful for audit and diagnostics even though it is
  not usable by automated model steps.
- The workflow may continue with other eligible or accepted sources after the
  rejected source is excluded.
