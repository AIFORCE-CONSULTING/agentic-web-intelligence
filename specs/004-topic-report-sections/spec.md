# Feature Specification: Topic-Scoped Report Sections

**Feature Branch**: `004-topic-report-sections`
**Created**: 2026-10-02
**Status**: Draft
**Input**: User description: "Revise final report generation so the platform owns the report structure and the model only drafts bounded topic-level findings. The platform should look up planned topics, find eligible and relevant source summaries per topic, assign simple citation labels, send one topic at a time to the model, require findings only for that supplied topic, reject invented topics and unsupported source labels, and render the final report and citation links deterministically."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Receive A Consistent Grounded Report (Priority: P1)

As an operator reviewing research results, I need the final report to contain the planned topic sections, cite the stored source summaries safely, and avoid failing just because the local model rewrites topic or source identifiers.

**Why this priority**: The report is the operator-facing synthesis of the research workflow. If the report is missing, sparse, or rejected because the model mishandled structure, the workflow does not deliver its main value.

**Independent Test**: Run a research task with multiple planned topics and qualified source summaries. The operator receives a final report whose sections match the planned topics and whose citation links point to stored source summaries.

**Acceptance Scenarios**:

1. **Given** a research run has planned topics and eligible, relevant source summaries assigned to those topics, **When** the final report is generated, **Then** the report contains one section for each planned topic in the planned order.
2. **Given** a topic has qualified source summaries, **When** the topic section is generated, **Then** findings may cite only the simple citation labels supplied for that topic.
3. **Given** the model attempts to create a new topic or cite a source label outside the supplied topic, **When** the platform validates the draft, **Then** the invalid material is rejected or corrected without allowing unsupported content into the report.

---

### User Story 2 - Understand Report Quality Problems (Priority: P2)

As an operator, I need report-quality failures to explain whether the issue was missing topic coverage, unsupported citations, malformed model output, timeout, or insufficient evidence, so I can decide whether to retry, adjust the research question, or inspect the source summaries directly.

**Why this priority**: Operators should not have to inspect logs to understand why a report is incomplete or why a fallback briefing was shown.

**Independent Test**: Force a report-generation attempt with malformed output, unsupported citations, and unavailable model conditions. The operator can see a report or fallback briefing with concise quality reasons and the stored source summaries remain available.

**Acceptance Scenarios**:

1. **Given** the model cites a label that was not supplied for the topic, **When** validation completes, **Then** the report-quality explanation identifies the unsupported citation problem in operator-readable language.
2. **Given** the model is unavailable or takes too long, **When** report generation ends, **Then** the operator receives a fallback evidence briefing with a visible failure reason rather than an absent report.

---

### User Story 3 - Preserve Traceability Without Overburdening The Model (Priority: P3)

As an operator or reviewer, I need citation links to remain traceable to stored source summaries, while the model is not responsible for choosing the report structure or source membership for each topic.

**Why this priority**: Traceability is important, but requiring a small local model to manage the entire report structure, topic IDs, and cross-topic citations made report creation brittle.

**Independent Test**: Inspect a completed report and verify that section headings, source lists, citation labels, and summary links are derived from stored research records rather than invented by the model.

**Acceptance Scenarios**:

1. **Given** a completed report, **When** a reviewer opens a citation link, **Then** it navigates to the stored source summary represented by that citation label.
2. **Given** a topic includes source summaries that are not cited by a model finding, **When** the report is rendered, **Then** the topic-level source list still discloses those sources.

### Edge Cases

- A planned topic has no qualified source summaries.
- A topic has many qualified summaries and only some are used in findings.
- The model returns a citation label with harmless formatting variation, such as lower case, while the label is otherwise unambiguous.
- The model returns a citation label that matches no supplied source.
- The model tries to add a new topic section or omit a planned topic.
- The model returns valid text but invalid structured data.
- The model is unavailable, times out, or returns no response.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST render final reports from the planned topic list rather than allowing the model to create, rename, reorder, or omit report sections.
- **FR-002**: The system MUST gather report input separately for each planned topic using only eligible, relevant, evidence-sufficient source summaries already assigned to that topic.
- **FR-003**: The system MUST assign simple, stable citation labels for the report input, such as `S01`, `S02`, and `S03`.
- **FR-004**: The system MUST give the model only one topic's source summaries at a time when requesting topic-level findings.
- **FR-005**: The system MUST require each model-drafted finding to cite only source labels supplied for the current topic.
- **FR-006**: The system MUST reject invented topics, unsupported source labels, and source labels from another topic.
- **FR-007**: The system MUST render citation links to stored source summaries using trusted platform data, not model-provided URLs or titles.
- **FR-008**: The system MUST render each topic's source list from trusted platform data, including qualified topic sources not cited by a finding.
- **FR-009**: The system MUST provide a final report or fallback evidence briefing whenever report inputs can be read and stored, even when model drafting fails.
- **FR-010**: The system MUST show concise report-quality reasons when the report receives a failure grade or fallback briefing.
- **FR-011**: The system MUST preserve report-attempt diagnostics sufficient to distinguish malformed output, unsupported citation labels, invented topics, model unavailability, and timeout conditions.
- **FR-012**: The system MUST keep source eligibility, topic qualification, human review, and trust-policy decisions outside model authority.

### Authority and Safety Boundaries *(include for agent, workflow, or external-action features)*

- **Authorized actors**: The operator requests research through the existing research workflow. The local model may draft topic-level findings only after the platform has selected the topic and fixed source set.
- **Human-only decisions**: Human review and overrides for evidence requiring review remain outside report generation. The model must not approve evidence, change trust decisions, or include blocked sources.
- **Agent limitations**: The model cannot query stored records, create report sections, decide source eligibility, invent topics, invent source labels, or provide final report links.
- **Canonical record**: Planned topics, qualified source summaries, report input snapshots, report attempts, report quality grade, and rendered report package remain the durable business records.
- **Operator-visible states**: The operator sees existing research progress states and then either a completed report with a pass/fail quality grade or a fallback evidence briefing with reasons.
- **Decision authority**: Platform rules decide topic sections, source membership, citation-label mapping, validation, rendering, and quality grade. The model proposes finding text and finding-to-source-label associations within one supplied topic.
- **Conflict outcome**: Stored topic and source records override model output. If a model draft disagrees with the stored record, the model output is rejected, corrected, or replaced with fallback content.
- **Excluded behavior**: This feature does not change search, extraction, trust policy, topic planning, source summarization, human review approval, or report-input eligibility rules.

### Key Entities *(include if feature involves data)*

- **Planned Topic**: A research topic already selected for the run. It defines the report section identity and order.
- **Topic Source Summary**: A stored source summary that is eligible, relevant, evidence-sufficient, and assigned to one planned topic.
- **Citation Label**: A simple report-local label, such as `S01`, that represents one stored source summary for citation and rendering.
- **Topic Finding Draft**: Model-drafted finding text for one planned topic, with citations selected only from that topic's supplied labels.
- **Rendered Report Package**: The operator-facing report or fallback evidence briefing, including topic sections, citation links, source lists, quality grade, reasons, and attempt diagnostics.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In test runs with qualified evidence for three planned topics, 100% of completed reports contain exactly those planned topics in the planned order.
- **SC-002**: In validation tests, 100% of invented topic IDs and unsupported source labels are rejected before appearing in an operator-facing report.
- **SC-003**: In test runs where the model changes source-label formatting harmlessly and unambiguously, at least 95% of cases are corrected or accepted without losing traceability.
- **SC-004**: In test runs where the model is unavailable or produces unusable topic findings, the operator receives a fallback evidence briefing instead of an absent report.
- **SC-005**: At least 90% of report-generation attempts with ten or more qualified source summaries produce either a passing report or a visible failure-grade report that still includes topic-organized evidence.

## Assumptions

- The existing research workflow already creates planned topics and assigns qualified source summaries to those topics.
- Source summaries remain the report input; raw webpage content is not sent to the final-report drafting step.
- A report-local label such as `S01` is easier for a small local model to copy consistently than labels such as `source-01`.
- The platform can safely normalize only harmless citation-label formatting differences when the intended source is unambiguous.
- The model may still fail or produce unusable output, so fallback evidence briefings remain required.
