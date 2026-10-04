# Feature Specification: Correct Report Exclusion Labels

**Feature Branch**: `008-fix-exclusion-labels`  
**Created**: 2026-10-03  
**Status**: Draft  
**Input**: User description: "There's an issue where the not_relevant label is being applied to sources where the extraction was blocked. The better fix is still modest: make the exclusion reason distinguish these cases cleanly: blocked_by_trust_policy, access_denied_by_publisher, unreachable, summary_failed, evidence_insufficient, not_relevant_to_planned_topics."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Understand Why a Source Was Not Used (Priority: P1)

As an operator reviewing a completed research report, I need the "Sources not used for report findings" section to explain the actual reason each source was excluded, so I do not mistake an access or extraction failure for a relevance decision.

**Why this priority**: The current wording can tell the operator that a source "did not become qualified evidence for a planned topic" even when the publisher blocked automated access. That undermines trust in the report and makes troubleshooting harder.

**Independent Test**: Complete a research run that includes a publisher-blocked source and verify the report labels that source as access-blocked rather than not relevant.

**Acceptance Scenarios**:

1. **Given** a discovered source rejects automated access before usable evidence is captured, **When** the final report lists excluded sources, **Then** the source is labeled as access denied by the publisher and not as not relevant.
2. **Given** a discovered source is blocked by the local trust workflow, **When** the final report lists excluded sources, **Then** the source is labeled as blocked by the local trust workflow.
3. **Given** a discovered source is captured, summarized, and then fails topic relevance, **When** the final report lists excluded sources, **Then** the source is labeled as not relevant to the planned topics.

---

### User Story 2 - Troubleshoot Report Gaps (Priority: P2)

As an operator reviewing report quality, I need exclusion labels to separate blocked access, unreachable content, summary failures, insufficient evidence, and relevance misses, so I can decide whether to retry, review manually, adjust the research question, or accept the report limitations.

**Why this priority**: Different exclusion causes require different operator responses. A publisher access denial is not solved the same way as a relevance miss or a failed summary.

**Independent Test**: Review a report containing multiple exclusion causes and verify each source has a distinct, plain-language explanation.

**Acceptance Scenarios**:

1. **Given** a source could not be reached or captured, **When** it appears in report exclusions, **Then** the explanation says that usable evidence was not captured.
2. **Given** a source summary failed, **When** it appears in report exclusions, **Then** the explanation says summary processing failed and does not imply the article was irrelevant.
3. **Given** captured content is insufficient, **When** it appears in report exclusions, **Then** the explanation says the evidence was insufficient for report findings.

---

### User Story 3 - Preserve Existing Report Workflow (Priority: P3)

As a platform maintainer, I need this correction to preserve existing report generation behavior, so the change improves clarity without altering trust decisions, extraction, summarization, topic relevance, or report composition.

**Why this priority**: This is a labeling and disclosure correction. It should not create a new workflow path or change which sources are allowed into model context.

**Independent Test**: Run existing report-generation scenarios and verify the same sources are included in report findings, while excluded-source labels become more specific.

**Acceptance Scenarios**:

1. **Given** a report has qualified supporting sources, **When** exclusion labels are corrected, **Then** the report findings and supporting-source list remain unchanged.
2. **Given** a source is excluded, **When** its exclusion reason is displayed, **Then** the reason reflects the existing stored outcome rather than a new model judgment.

### Edge Cases

- A source may be blocked by the platform's trust workflow before publisher access is attempted; it must be labeled as a trust-policy block rather than publisher access denial.
- A source may be unreachable due to timeout, network failure, empty extraction, or HTTP errors; the operator-facing label must avoid claiming the source was semantically irrelevant unless usable content was actually evaluated for relevance.
- A source may be captured and summarized but fail topic relevance; this is the only case that should use the "not relevant to planned topics" meaning.
- A source may have a stored summary from a previous run but be unreachable in the current run; the report exclusion for the current run must describe the current run outcome.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST distinguish report exclusion reasons using the canonical reason codes `blocked_by_trust_policy`, `access_denied_by_publisher`, `unreachable`, `summary_failed`, `evidence_insufficient`, and `not_relevant_to_planned_topics`.
- **FR-002**: The system MUST reserve "not relevant to planned topics" for sources that had usable evidence, completed summary processing, and then failed topic relevance for the current report.
- **FR-003**: The system MUST label publisher or website access denial separately from local trust-policy blocking.
- **FR-004**: The system MUST present each exclusion reason in plain business language that helps an operator understand what happened without reading logs.
- **FR-005**: The system MUST preserve the report's supporting-source list, report findings, trust outcomes, extraction outcomes, summary artifacts, and topic relevance decisions.
- **FR-006**: The system MUST make the exclusion reason available anywhere report exclusions are retrieved or displayed, not only in one UI view.
- **FR-007**: The system MUST continue to disclose excluded sources even when no stored summary exists for that source.
- **FR-008**: The system MUST avoid introducing a new workflow state, authority decision, human-review path, or model-owned classification to explain exclusions.

### Authority and Safety Boundaries *(include for agent, workflow, or external-action features)*

- **Authorized actors**: Operators may view report exclusions and their explanations. No new actor receives permission to change trust, extraction, summary, relevance, or report state.
- **Human-only decisions**: This feature does not add or change human approvals, acceptances, rejections, or overrides.
- **Agent limitations**: The local model does not decide why an excluded source was excluded. Exclusion reasons are derived from existing platform records.
- **Canonical record**: The report exclusion attached to the stored report is the operator-facing disclosure record for why a source did not contribute findings. Underlying source, preflight, trust, summary, evidence sufficiency, and relevance records remain the business records that determine the reason.
- **Operator-visible states**: Operators should see distinct explanations for local policy block, publisher access denial, unreachable content, summary failure, insufficient evidence, and not relevant to planned topics.
- **Decision authority**: Platform rules derive the exclusion reason from existing records. The model may not rewrite or infer the exclusion reason.
- **Conflict outcome**: If records disagree, the system must prefer the earliest decisive non-model outcome that prevented usable report evidence, such as trust block or access failure, before falling back to relevance wording.
- **Excluded behavior**: This feature does not retry extraction, bypass publisher controls, change trust policy, regenerate summaries, re-run relevance decisions, or alter the final report's findings.

### Key Entities *(include if feature involves data)*

- **Report Exclusion**: A source disclosed in a report because it did not contribute to report findings. Key attributes include source title, source URL, reason code, and operator-facing reason.
- **Source Preflight Outcome**: The recorded result of checking whether a discovered source can be captured and whether it passes local trust workflow rules.
- **Summary Outcome**: The recorded result of summarization for a captured evidence version, including failures and evidence sufficiency.
- **Topic Relevance Outcome**: The recorded result that determines whether a completed summary counts toward a planned topic.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of publisher-blocked or unreachable sources in report exclusions are labeled without using "not relevant" wording.
- **SC-002**: 100% of sources labeled "not relevant to planned topics" have completed usable summary processing before that label is applied.
- **SC-003**: Operators can distinguish at least six exclusion categories in the report without consulting logs.
- **SC-004**: Existing report inclusion behavior remains unchanged for qualified supporting sources.
- **SC-005**: Regression tests cover all six exclusion categories using stored outcomes rather than model-generated explanations.

## Assumptions

- The current issue is primarily an explanation and classification bug, not a failure in extraction, trust policy, summarization, topic relevance, or report generation.
- The feature should use existing stored outcomes to determine the explanation.
- Publisher access denial includes cases where the source rejects automated access, such as HTTP 403, when that information is available from existing records.
- If existing records do not contain enough detail to distinguish publisher access denial from generic unreachable content, the system may use the broader "unreachable" explanation until richer retrieval details are available.
