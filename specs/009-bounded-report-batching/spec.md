# Feature Specification: Bounded Final Report Batching

**Feature Branch**: `009-bounded-report-batching`  
**Created**: 2026-10-04  
**Status**: Draft  
**Input**: User description: "Fix final report generation when one topic has many qualified summaries. The latest failed run sent 15 summaries and 22,307 characters to the model for one topic, and both attempts returned `{}`. Previous successful report sections used 7 summaries and about 10k characters. Focus the fix on bounded report batching: cap topic-report inputs per model call around 5-7 summaries, generate smaller validated finding batches for large topics, merge validated findings deterministically, keep the final report structure platform-owned, and tighten empty-output recovery."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Generate a Report for Large Topic Evidence (Priority: P1)

As an operator reviewing a research run, I want the final report to be generated even when one planned topic has many qualified source summaries, so that a large evidence set does not collapse into an empty or failed report section.

**Why this priority**: The current failure prevents the operator from getting a useful report after successful search, evidence capture, trust review, summarization, and topic qualification. The report step should be resilient to a single topic having more summaries than the local model can reliably handle in one pass.

**Independent Test**: Can be tested with a research run where one topic has at least 15 qualified summaries. The report should contain findings for that topic, cite stored summaries, and avoid using an empty model response as the topic section.

**Acceptance Scenarios**:

1. **Given** one planned topic has 15 qualified summaries, **When** the report is generated, **Then** the topic is processed in bounded groups and the final report includes validated findings for that topic.
2. **Given** a report generation attempt returns an empty response such as `{}`, **When** retry feedback is prepared, **Then** the next attempt clearly treats the empty response as invalid and asks for findings based on the supplied summaries.
3. **Given** at least one bounded group for a large topic produces valid findings, **When** another group fails after retry, **Then** the final report still renders the valid findings and records a quality reason for the failed group.

---

### User Story 2 - Preserve Platform-Owned Report Structure (Priority: P2)

As an operator, I want the final report structure and citations to remain controlled by the platform, so that report sections, source lists, and links remain predictable even when the model drafts only smaller pieces of text.

**Why this priority**: The platform already moved toward safer report generation by owning topics, source assignment, citation labels, and final rendering. Batching must not reintroduce model ownership of report structure or source selection.

**Independent Test**: Can be tested by comparing the stored topic plan, qualified source list, report sections, and rendered citations. The final report should preserve the planned topic order and source links regardless of how many bounded model calls were needed.

**Acceptance Scenarios**:

1. **Given** a topic is split into multiple bounded report groups, **When** all groups finish, **Then** the final rendered report has one coherent section for the topic, not separate model-authored subreports.
2. **Given** the model cites a source label that was not supplied to a bounded group, **When** that group is validated, **Then** the unsupported citation is rejected and not rendered as a valid claim.
3. **Given** a topic has qualified summaries that were not cited by a generated finding, **When** the report is rendered, **Then** the deterministic source list still links back to the stored summaries for that topic.

---

### User Story 3 - Explain Report Quality Clearly (Priority: P3)

As an operator, I want report-quality messages to explain whether a report is complete, partially degraded, or failed, so that I can distinguish model drafting limitations from search, trust, extraction, or summary failures.

**Why this priority**: A report can be useful even when one bounded group fails. Operators need concise explanations that identify which topic or source group had trouble without implying that earlier workflow stages failed.

**Independent Test**: Can be tested by forcing one bounded report group to fail while others pass. The final report should render available findings and show a quality grade and reasons that identify the specific report-generation limitation.

**Acceptance Scenarios**:

1. **Given** all bounded groups produce validated findings, **When** the report is shown, **Then** report quality is marked as passing.
2. **Given** some bounded groups produce validated findings and some fail, **When** the report is shown, **Then** report quality explains the partial degradation without hiding the valid findings.
3. **Given** all bounded groups for a topic fail, **When** the report is shown, **Then** the topic falls back to stored evidence and the quality reason identifies empty or invalid model findings as the report-stage issue.

### Edge Cases

- A topic has fewer summaries than the bounded group size and should be processed as one normal group.
- A topic has exactly the bounded group size and should not be split unnecessarily.
- A topic has more summaries than the bounded group size and must be split without losing any qualified source.
- A topic has one very long summary that exceeds the configured character budget by itself; that source should be isolated in its own bounded group rather than dropped.
- A topic has several summaries that are individually small but collectively exceed the configured character budget; the planner should split before the oversized prompt is created.
- A model response is valid JSON but contains no findings.
- A model response contains findings but no usable source references.
- A model response cites a source label from a different bounded group.
- One bounded group repeatedly fails while other groups for the same topic succeed.
- No bounded group for a topic produces a valid finding.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST limit the amount of qualified source-summary material sent to one report-drafting attempt for a topic using both a maximum number of summaries and a maximum prompt input character budget.
- **FR-002**: The system MUST split a large topic into bounded source groups when the topic has more qualified summaries than the configured report-drafting summary limit or when the next summary would exceed the configured prompt input character budget.
- **FR-003**: The system MUST preserve every qualified source summary as either part of a bounded report-drafting group or part of the deterministic topic source list.
- **FR-004**: The system MUST validate each bounded group response before allowing its findings into the final report.
- **FR-005**: The system MUST reject empty report-drafting responses as invalid findings, including responses that are otherwise structurally parseable.
- **FR-006**: The system MUST provide retry feedback that clearly explains why an empty or invalid report-drafting response was rejected.
- **FR-007**: The system MUST merge validated findings from multiple bounded groups into one operator-facing topic section.
- **FR-008**: The system MUST keep topic order, topic titles, source assignment, citation labels, citation links, and final report rendering under platform control.
- **FR-009**: The system MUST prevent findings from citing sources that were not supplied to the bounded group that produced the finding.
- **FR-010**: The system MUST render a deterministic source list for each topic using the stored qualified summaries, regardless of whether every source was cited in a finding.
- **FR-011**: The system MUST record report-attempt telemetry for each bounded group, including the topic, group position, attempt number, prompt input character count, duration, validation outcome, failure reason, raw response, and response character count.
- **FR-012**: The system MUST distinguish report-stage quality problems from search, acquisition, trust, relevance, and source-summary failures.
- **FR-013**: The system MUST allow a final report to be created from successful bounded groups even when another bounded group fails, while clearly marking report quality as degraded.
- **FR-014**: The system MUST fall back to stored evidence for a topic only when no bounded group for that topic produces validated findings.
- **FR-015**: The system MUST avoid making the model responsible for selecting topics, deciding which sources belong to a topic, or rendering final report structure.

### Authority and Safety Boundaries *(include for agent, workflow, or external-action features)*

- **Authorized actors**: The operator requests a report by running the existing research workflow. The platform may perform bounded report-drafting attempts using already stored, eligible, relevant summaries.
- **Human-only decisions**: This feature does not add any new human approval or override decision.
- **Agent limitations**: The model may draft findings only from the bounded summaries supplied for one topic group. It may not choose topics, fetch sources, change source eligibility, change report quality, or decide final citations.
- **Canonical record**: Stored research topics, qualified source summaries, report inputs, report attempts, report quality reasons, report contributions, and the rendered report remain the durable records for this feature.
- **Operator-visible states**: The operator continues to see the existing research workflow states. Report quality explains whether the report passed, is partially degraded, or used stored-evidence fallback for a topic.
- **Decision authority**: The model proposes bounded findings. Platform validation decides whether those findings can be used. The platform renders the final report and assigns report quality.
- **Conflict outcome**: If a bounded model response conflicts with stored topic or source assignments, the response is rejected and the report records a report-stage quality reason.
- **Excluded behavior**: This feature does not change search, extraction, trust policy, human evidence review, source summaries, keyword generation, topic planning, or model selection.

### Key Entities *(include if feature involves data)*

- **Report Bounded Group**: A subset of qualified source summaries for one planned topic that is small enough to send to one report-drafting attempt.
- **Report Finding Attempt**: One attempt to generate findings for a bounded group, including validation outcome, timing, prompt input character count, response character count, and failure explanation.
- **Validated Finding**: A model-drafted statement that passed platform checks and cites only source labels supplied to its bounded group.
- **Topic Report Section**: The final operator-facing section for one planned topic, assembled by the platform from validated findings and deterministic source links.
- **Report Quality Reason**: A concise explanation of any report-stage degradation, tied to a topic or bounded group when applicable.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A topic with 15 qualified summaries generates an operator-visible report section with validated findings instead of failing only because the topic was too large for one model call.
- **SC-002**: Empty report-drafting responses such as `{}` are rejected 100% of the time and recorded with a clear report-stage reason.
- **SC-003**: In test runs where at least one bounded group succeeds for a topic, the final report includes those successful findings and does not discard them because another group failed.
- **SC-004**: All rendered finding citations link to stored summaries that were supplied to the bounded group that produced the finding.
- **SC-005**: Operators can identify whether a report problem came from the report-drafting stage without confusing it with search, extraction, trust, relevance, or summary failures.

## Assumptions

- The existing report structure, topic plan, source labels, and stored summaries remain the foundation for final reports.
- The first version should use conservative grouping defaults aligned with observed successful report attempts: no more than seven summaries per group and no more than roughly 10,000 prompt input characters per group, unless a single summary exceeds that character budget by itself.
- A partially degraded report is more useful than no report when validated findings exist.
- The feature should improve reliability without changing earlier research workflow stages.
