# Data Model: Bounded Final Report Batching

## Existing Entities Reused

### Research Run

- **Canonical record**: `research_runs`
- **Purpose**: Operator-facing workflow status for the research task.
- **Relevant fields**: `status`, `status_version`, `failed_stage`,
  `failure_code`, `failure_explanation`, `retryable`.
- **Owner**: `ResearchStore.transition_status`.
- **Change**: No schema or transition change.

### Report Input

- **Canonical record**: `agentic_research_report_inputs`
- **Purpose**: Frozen snapshot of qualified source summaries that were eligible
  to support one stored report package.
- **Relevant fields**: report ID, topic identity, source label, source URL,
  title, summary text, artifact ID, content hash, position.
- **Owner**: `ResearchReportingService` through `AgenticResearchStore.save_report_package`.
- **Change**: No schema change required. Bounded groups reference the existing
  source labels rather than copying source membership elsewhere.

### Report Package

- **Canonical record**: `agentic_research_reports`
- **Purpose**: Stored operator-facing report package.
- **Relevant fields**: `markdown`, `quality_grade`, `quality_reasons`,
  `report_origin`, `input_fingerprint`, prompt and contract versions.
- **Owner**: `ResearchReportingService` through `AgenticResearchStore.save_report_package`.
- **Change**: No required schema change. `quality_reasons` may include
  bounded-group-specific messages when a group fails.

### Report Contribution

- **Canonical record**: `agentic_research_report_contributions`
- **Purpose**: Trace accepted findings and deterministic section source lists
  back to stored source labels and topic records.
- **Owner**: `ResearchReportingService` through `AgenticResearchStore.save_report_package`.
- **Change**: Reuse existing contribution reasons. Accepted bounded-group
  findings still record finding contributions; deterministic source lists still
  record section-source-list contributions.

## Entities Extended

### Report Finding Attempt

- **Canonical record**: `agentic_research_report_attempts`
- **Purpose**: Diagnostic record for one bounded report-drafting attempt.
- **Existing fields**: `report_id`, `topic_id`, `attempt_number`, `status`,
  `input_fingerprint`, `model_name`, `prompt_version`, `contract_version`,
  `raw_response`, `validation_errors`, `duration_ms`, `input_characters`,
  `failure_code`.
- **New fields**:
  - `group_index`
  - `response_characters`
- **Validation rules**:
  - `group_index` is one-based for bounded report groups.
  - Attempt identity is unique by `report_id`, `topic_id`, `group_index`, and
    `attempt_number`.
  - `attempt_number` remains bounded to the existing maximum correction policy.
  - `input_characters` records the bounded group payload size, not the complete
    topic payload size.
  - `response_characters` records the character length of the raw model
    response for the attempt, including empty JSON responses such as `{}`.
  - Empty responses such as `{}` are stored as unusable attempts with an
    explicit empty-output validation reason.
- **Relationships**:
  - Belongs to one report package.
  - Identifies the topic and bounded group that produced the attempt.
  - Accepted attempts may create report contributions for cited source labels.

## New In-Memory Concepts

### Report Bounded Group

- **Purpose**: Execution packaging for a subset of one topic's qualified source
  summaries.
- **Fields**:
  - `topic_id`
  - `group_index`
  - ordered report inputs
  - input character count
  - oversized-single-source indicator when one summary exceeds the target
    character budget by itself
- **Persistence**: Does not require a new table. Group identity is persisted on
  each report attempt.
- **Validation rules**:
  - Every qualified source summary for a topic appears in exactly one bounded
    group for a report package.
  - A topic with summaries at or below the configured summary-count and
    character-budget limits has exactly one group.
  - A topic with summaries above either configured limit is split into multiple
    ordered groups.
  - A single oversized summary is isolated in its own group and remains eligible
    for validation rather than being dropped.

### Validated Group Finding

- **Purpose**: Model-proposed finding that passed validation for one bounded
  group.
- **Fields**:
  - finding text
  - normalized source labels
  - topic ID
  - group index
  - finding position within the final topic section
- **Persistence**: Rendered into report Markdown and traced through report
  contribution rows.
- **Validation rules**:
  - Must cite one or more labels supplied to the same bounded group.
  - Must not cite labels from another topic or another bounded group.
  - Must not be accepted if the group draft has no findings.

## State and Quality Rules

- A report package can be stored when report inputs are readable and persistence
  succeeds, even if one or more bounded groups fail.
- `quality_grade = PASS` only when all required topic/group checks pass.
- `quality_grade = FAIL` may still include validated findings from successful
  groups.
- `report_origin = model_pass` when all sections are fully supported by accepted
  findings.
- `report_origin = model_fail` when at least one accepted finding exists but one
  or more report-stage quality reasons remain.
- `report_origin = fallback` when no topic receives accepted findings and the
  report uses stored evidence fallback.
