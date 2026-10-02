# Feature Specification: Grounded Final Reports

**Feature Branch**: `003-improve-final-report`  
**Created**: 2026-10-01  
**Status**: Draft  
**Input**: User description: "Improve final research reports so they accurately and traceably represent all eligible, topic-qualified source summaries, include every planned topic, disclose completed summaries excluded from report input, and avoid unsupported or misleading source characterizations."

## Clarifications

### Session 2026-10-01

- Q: How should the report make its source attribution visible? -> A: Important factual claims include direct source links, and every planned-topic section includes a linked list of all contributing sources.
- Q: How detailed should the final report be? -> A: A detailed research briefing of approximately 1,200-1,800 words.
- Q: What should happen when a generated report is incomplete? -> A: Retry once with specific feedback. If it remains incomplete, store and show the best structurally safe evidence-grounded report with a `FAIL` quality grade and concise reasons; use a fallback evidence briefing when no model draft is safe. The research run fails only when the platform cannot read inputs or store the report package.
- Q: How should a completed source excluded from report input be handled? -> A: List it separately with a concise, useful reason that identifies the planned topic or topics assessed and why it did not qualify; do not add it to the report automatically.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Receive a Complete Evidence-Grounded Report (Priority: P1)

As an operator, I want the final report for my research question to cover the important findings from every eligible, topic-qualified source summary, so that I can rely on it as a balanced account of the evidence rather than a short collection of generic observations.

**Why this priority**: The current report can accurately repeat broad themes while omitting important technical, commercial, operational, and public-interest findings that the platform has already summarized. This gives an incomplete picture of the research question. A detailed 1,200-1,800 word briefing provides enough room to represent those findings without becoming a source-by-source transcript.

**Independent Test**: Use a research task with qualified summaries covering distinct technical, user-experience, ethical, commercial, and operational findings. Confirm that the resulting report includes a substantive finding from each qualified summary or identifies that summary as contributing to a named consolidated finding.

**Acceptance Scenarios**:

1. **Given** a research task has qualified summaries for every planned topic, **When** its final report is generated, **Then** the report contains a distinct, clearly labeled discussion of each planned topic.
2. **Given** qualified summaries contain findings that are not repeated by other summaries, **When** the report is generated, **Then** those distinct findings are included or are explicitly connected to the report section where they were consolidated.
3. **Given** qualified sources span technical infrastructure, user experience, governance, commerce, and operational adoption, **When** the operator reads the report, **Then** no one category is presented as the entire answer merely because it is easier to summarize.
4. **Given** a draft report is missing a required topic section, source contribution, attribution, or required level of detail, **When** the platform detects the omission, **Then** it makes one corrective attempt that identifies the missing requirement.
5. **Given** the corrective report attempt still does not meet report requirements, **When** the attempt ends, **Then** the operator receives the best usable evidence-grounded report with a visible `FAIL` quality grade and concise reasons; the completed source summaries remain available.

---

### User Story 2 - Trace Report Claims to Stored Sources (Priority: P1)

As an operator, I want to see which stored sources support the findings in the final report, so that I can inspect the underlying source summary and judge its relevance and credibility.

**Why this priority**: A report without usable source attribution makes it impossible to distinguish evidence-grounded conclusions from over-compression or mistaken model wording.

**Independent Test**: Generate a report from several qualified source summaries. Confirm that each substantive factual finding is accompanied by a usable source attribution and that an operator can open the linked stored source summary from the report.

**Acceptance Scenarios**:

1. **Given** a report includes an important factual claim or concrete recommendation drawn from a source summary, **When** an operator selects its direct attribution, **Then** the operator can open the corresponding stored source summary.
2. **Given** several sources support one consolidated finding, **When** the finding appears in the report, **Then** the report identifies each contributing source rather than implying a single source supports the whole conclusion.
3. **Given** a source summary describes a product, tool, example, or organization, **When** the report refers to it, **Then** the report preserves that relationship and does not relabel it as a framework, control, standard, or other materially different kind of thing.

---

### User Story 3 - Understand What the Report Did Not Use (Priority: P2)

As an operator, I want a clear account of completed source summaries that were not used in the final report, so that I understand the report's scope and can investigate a potentially surprising exclusion.

**Why this priority**: A completed source may be excluded because it did not qualify for a planned topic. Without disclosure, the operator may reasonably assume every completed source informed the report.

**Independent Test**: Create a research task with at least one completed source summary that is not qualified for report use. Confirm that the report identifies the source, says it was excluded from automated findings, and does not treat it as report evidence.

**Acceptance Scenarios**:

1. **Given** a source has a completed summary but is not eligible for report input, **When** a report is generated, **Then** the operator can see the source title, URL, planned topic or topics assessed, and a concise, useful reason it was excluded.
2. **Given** a source was blocked, requires review, has insufficient evidence, or was judged irrelevant to every planned topic, **When** a report is generated, **Then** it is listed separately from the report's supporting sources.
3. **Given** no qualified summaries exist for a planned topic, **When** the report is generated, **Then** the report plainly states that the topic lacks sufficient evidence rather than filling the section with unsupported generalizations.

### Edge Cases

- Several qualified sources make similar claims but use different terminology.
- A qualified source contains a significant caveat, limitation, or disagreement that is not shared by the other sources.
- One source supports more than one planned topic.
- A completed source is relevant in a broad sense but did not qualify for any planned topic.
- A source's wording is ambiguous enough that a report could misidentify a product, protocol, framework, organization, or control.
- The report has many qualified sources, but its length must remain readable for an operator.
- A report-generation failure occurs after source summaries and topic coverage are complete.
- A draft report does not include every planned-topic section, enough detail, or the required source attribution.
- A corrective report fixes one missing requirement but omits another.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The platform MUST generate the final report from only source summaries that have passed the platform's existing eligibility, relevance, and evidence-sufficiency requirements.
- **FR-002**: The report MUST include a clearly labeled section for every planned topic, including topics that lack qualified evidence.
- **FR-003**: Every important factual claim or concrete recommendation in the report MUST include a direct attribution to its supporting stored source summary or summaries.
- **FR-004**: The report MUST cover meaningful source-specific findings, examples, limitations, or caveats when they add information beyond the broad themes shared by other qualified sources.
- **FR-005**: The report MUST balance planned topics according to the available evidence and MUST NOT allow generic governance or user-experience themes to crowd out qualified technical, commercial, operational, public-interest, or other distinct findings.
- **FR-006**: Every planned-topic section MUST include a linked list of all qualified sources that contributed to that section, including sources whose contribution was consolidated into a shared finding.
- **FR-006a**: Each direct attribution and each topic-section source list entry MUST identify the source in a way that lets an operator open the associated stored source summary.
- **FR-007**: The report MUST preserve the factual role stated in the source summary when describing a product, protocol, framework, organization, standard, or example. It MUST NOT present a source-specific example as a generally established control or framework without evidence.
- **FR-008**: The report MUST distinguish evidence-backed findings from the report's synthesis. It MUST not add unsupported facts, recommendations, or source characterizations.
- **FR-009**: The report MUST separately disclose every completed source summary that was excluded from report input, including the source identity, the planned topic or topics assessed, and a concise, useful recorded reason it was excluded.
- **FR-009a**: An exclusion reason for a completed source MUST identify why the source did not qualify for the named planned topic or topics, rather than using a generic statement that the source was not used.
- **FR-010**: The report MUST separately disclose sources that were unavailable, blocked, awaiting human review, insufficient, or otherwise omitted from automated findings, without treating those sources as support for the report.
- **FR-011**: When no qualified source supports a planned topic, the report MUST say that evidence is insufficient for that topic and MUST not create a substitute conclusion from unrelated sources.
- **FR-012**: The operator MUST be able to distinguish the report's supporting sources from excluded sources without reading system logs or inspecting internal workflow records.
- **FR-013**: Regenerating a report from unchanged qualified summaries MUST not change which sources are considered eligible report input. Any difference in wording or emphasis remains attributable to the recorded report generation attempt.
- **FR-014**: For a research task with ten or more qualified report sources, a `PASS` report narrative MUST contain approximately 1,200-1,800 words, excluding linked source lists and source-exclusion disclosures. A shorter narrative receives a `FAIL` quality reason. Reports with fewer qualified sources may be shorter but remain subject to every source-contribution and attribution requirement.
- **FR-015**: The platform MUST check a draft report for its required planned-topic sections, source contributions, direct attributions, source lists, scope disclosures, and required level of detail, then assign a visible report-quality grade of `PASS` or `FAIL`.
- **FR-016**: When a draft report does not meet a report requirement, the platform MUST make no more than one corrective attempt and identify the unmet requirement. The corrective attempt improves the report when possible; it does not remove the operator's access to an evidence-grounded report.
- **FR-017**: When the corrective attempt also does not meet report requirements, the platform MUST save and display the best usable report with a `FAIL` quality grade, preserve the completed source summaries and source-exclusion information, and show concise reasons for the failed quality checks.
- **FR-017a**: When neither model response can be used, including when the local model is unavailable or returns malformed output, the platform MUST generate and store a clearly labeled fallback evidence briefing from the fixed qualified source summaries and planned topics. The fallback MUST receive a `FAIL` quality grade that explains why no validated model synthesis was available.
- **FR-017b**: The research workflow MUST become failed during reporting only when the platform cannot read the report inputs or store the report package. A `FAIL` report-quality grade alone MUST NOT make the research run fail.
- **FR-017c**: A `PASS` report-quality grade means the report passed the platform's coverage, traceability, structure, and detail checks. It MUST NOT be represented as independent fact verification of every natural-language statement.
- **FR-017d**: A model draft is eligible to become a `FAIL` report only when it is structurally safe to render: it matches the report schema, every factual finding has at least one known source reference in its allowed topic scope, and it contains no finding in an insufficient-evidence section. Among structurally safe failing drafts, the platform MUST choose the draft with the most passed equal-weight quality checks: planned-topic coverage, qualified-source representation, and applicable narrative length. A tie MUST select the corrective second attempt. A draft that is not structurally safe MUST be replaced by the platform fallback briefing.

### Authority and Safety Boundaries *(include for agent, workflow, or external-action features)*

- **Authorized actors**: An authenticated operator may start research through the existing research action. The platform may create one final report after the existing research workflow has reached the reporting stage.
- **Human-only decisions**: Human evidence acceptance and trust-policy decisions remain outside report generation. The report cannot approve blocked or review-required evidence.
- **Agent limitations**: The local model may draft only from the platform-supplied qualified summaries and topic records. It cannot select new sources, change source eligibility, change topic relevance, invent source links, alter a source's stored summary, or declare excluded evidence qualified.
- **Canonical record**: The stored research report is the operator-facing report for a research task. Its recorded `quality_grade` and `quality_reasons` are the authoritative answer to whether it passed the report-quality contract. Existing stored source summaries, topic-coverage decisions, and source exclusion outcomes remain the authoritative basis for what may appear in or be excluded from the report.
- **Operator-visible states**: During reporting, the operator sees that the report is being prepared. On completion, the operator sees the grounded report, its `PASS` or `FAIL` quality grade, supporting sources, and exclusions. The research workflow fails only when a report package cannot be read or stored; completed source summaries remain available for review.
- **Decision authority**: Platform rules decide whether a summary qualifies as report input and which exclusions must be disclosed. The local model drafts the narrative and source contributions only from that fixed input. A human retains existing authority over evidence requiring review.
- **Conflict outcome**: If a saved report and its stored source basis disagree, the stored source basis controls. The report is treated as outdated and must not be represented as a current complete account until regenerated from the current qualified input set.
- **Excluded behavior**: This feature does not change search, retrieval, trust-policy enforcement, source-summary creation, topic-planning, relevance decisions, human review, or the operator's existing Discover Sources action.

### Key Entities *(include if feature involves data)*

- **Qualified report source**: A stored source summary that has passed evidence eligibility, topic relevance, and evidence-sufficiency requirements and may support the final report.
- **Source contribution**: The visible connection between a qualified report source and the report finding or topic section that uses its material.
- **Excluded completed source**: A source with a stored summary that was not passed into report generation because it did not qualify for a planned topic or another recorded policy decision excluded it.
- **Report scope disclosure**: The operator-facing account of sources and topics that were not used for automated findings, together with the planned topic or topics assessed and their concise, useful recorded reason.
- **Report-quality grade**: A platform-generated `PASS` or `FAIL` assessment of whether the report met its coverage, traceability, structure, and detail contract. It is not a claim that the platform independently fact-checked every sentence.
- **Quality reason**: A platform-generated object with a stable reason code and concise explanation of one deterministic report check or fallback cause, such as an omitted topic section, unrepresented qualified source, insufficient narrative detail, unavailable model, malformed model response, or unsafe model draft.
- **Report origin**: A platform-generated value identifying whether the stored report came from a passing model draft (`model_pass`), a structurally safe but incomplete model draft (`model_fail`), or the platform fallback evidence briefing (`fallback`).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In a representative research task containing qualified sources across at least three planned topics, 100% of qualified report sources appear in the linked source list for at least one planned-topic section.
- **SC-002**: In a representative research task containing a completed but excluded source summary, 100% of such exclusions are visible to the operator with the source identity, planned topic or topics assessed, and concise, useful exclusion reason.
- **SC-003**: In review of a representative report with distinct technical, user-experience, ethical, commercial, and operational findings, each finding category present in qualified evidence appears in the appropriate planned-topic discussion or is explicitly identified as not sufficiently supported.
- **SC-004**: An operator can open the stored source summary supporting any substantive report finding in no more than one selection from the report.
- **SC-005**: A review of representative reports finds no case where a product, tool, example, or organization is labeled as a materially different type of entity without supporting evidence.
- **SC-006**: A report based on unchanged qualified sources does not imply that excluded, blocked, review-required, insufficient, or unavailable sources support its findings.
- **SC-007**: In representative research tasks with ten or more qualified report sources, every `PASS` final report narrative is between 1,200 and 1,800 words, excluding source lists and source-exclusion disclosures.
- **SC-008**: In a test where the first report draft omits a required report element and the second draft corrects it, the operator receives the corrected report with a `PASS` quality grade.
- **SC-009**: In a test where both permitted report drafts omit a required report element, the operator receives the best usable evidence-grounded report with a `FAIL` quality grade, concise reasons, and access to 100% of completed source summaries and exclusions.
- **SC-010**: In a test where the local model is unavailable or produces malformed output twice, the operator receives a clearly labeled fallback evidence briefing with a `FAIL` quality grade rather than an absent report, provided the platform can read and store the report inputs.

## Assumptions

- The existing research workflow remains responsible for deciding when report generation begins and for preserving the current source eligibility, trust, relevance, and coverage boundaries.
- The feature improves the quality, completeness, traceability, and scope disclosure of the existing final report; it does not broaden which evidence is allowed into automated model context.
- Source attribution should be readable in the rendered report and link to the existing stored source-summary experience rather than requiring the operator to interpret raw database records.
- When many sources support the same point, the report may consolidate them, provided it visibly identifies every contributing qualified source and does not lose important differences or caveats.
- The final report is a detailed research briefing of approximately 1,200-1,800 words when ten or more qualified report sources are available, excluding source lists and source-exclusion disclosures. Smaller evidence sets may produce shorter reports. Concision never justifies omitting a qualified source's distinct material or concealing that the evidence is insufficient.
- A completed excluded source remains outside automated report evidence. A surprising exclusion may identify a separate topic-relevance issue, but this feature does not override relevance decisions or add a new operator approval step.
