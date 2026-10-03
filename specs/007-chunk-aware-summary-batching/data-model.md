# Data Model: Chunk-Aware Summary Batching

No new database table is planned for this feature. The design uses existing
summary work records and makes their ownership clearer.

## Summary Work Group

**Purpose**: Represents one bounded unit of source summary work.

**Existing records**:

- `evidence_summary_executions.id`
- `evidence_summary_executions.workspace_id`
- `evidence_summary_executions.run_id`
- `evidence_summary_executions.route`
- `evidence_summary_executions.status`
- `evidence_summary_execution_sources.execution_id`
- `evidence_summary_execution_sources.url`
- `evidence_summary_work_set_members.work_set_id`
- `evidence_summary_work_set_members.execution_id`

**Validation rules**:

- A work group must contain at least one source.
- A work group must not contain more than the configured maximum source count.
- A work group must not exceed 15 total chunks unless it contains exactly one
  oversized source.
- A source with 16 or more chunks is oversized and must be isolated in its own
  work group without being blocked.
- The same source URL should appear at most once in a work group.

## Source Chunk Metadata

**Purpose**: Records the observed amount of work for one source.

**Existing records**:

- `evidence_summary_execution_sources.content_characters`
- `evidence_summary_execution_sources.chunk_count`
- `evidence_summary_execution_sources.chunking_policy_version`
- `evidence_summary_execution_sources.content_hash`

**Validation rules**:

- `chunk_count` must be at least 1 after successful extraction/preparation.
- The chunking policy version must identify the deterministic chunk policy used.
- Batch planning must use the chunk count for the evidence version assigned to
  the execution.

## Summary Work Set

**Purpose**: Represents the whole summary stage for one research run.

**Existing records**:

- `evidence_summary_work_sets.id`
- `evidence_summary_work_sets.workspace_id`
- `evidence_summary_work_sets.run_id`
- `evidence_summary_work_sets.status`
- `evidence_summary_work_sets.completed_at`

**State transitions**:

```text
created -> waiting
waiting -> completed    when all member executions are terminal and at least one completed
waiting -> failed       when all member executions are terminal and none completed
completed -> completed  terminal
failed -> failed        terminal
```

**Validation rules**:

- A work set remains `waiting` until every member execution is terminal.
- A work set is `completed` when at least one member execution completed with
  usable source summaries.
- A work set is `failed` when no member execution produced usable summaries.

## Source Summary Status

**Purpose**: Identifies whether one source can contribute to coverage/reporting.

**Existing records**:

- `evidence_summary_execution_sources.status`
- `evidence_summary_execution_sources.summary`
- `evidence_summary_execution_sources.keywords`
- `evidence_summary_execution_sources.evidence_sufficient`
- `evidence_summary_execution_sources.failure_reason`
- `evidence_summary_execution_sources.failure_category`
- `evidence_summary_execution_sources.artifact_id`

**State transitions**:

```text
pending -> extracting -> extracted -> summarizing -> completed
pending -> extracting -> extracted -> summarizing -> failed
extracted -> completed  when a reusable artifact is linked
completed -> completed  terminal for this execution
failed -> failed        terminal for this execution
```

**Validation rules**:

- Only `completed` sources with sufficient evidence may produce report inputs.
- Failed sources must retain an operator-readable failure reason/category.
- A failed source must not create topic coverage or report input rows.

## Research Run Status

**Purpose**: Official operator-facing workflow state.

**Existing records**:

- `research_runs.status`
- `research_runs.status_version`
- `research_runs.failed_stage`
- `research_runs.failure_code`
- `research_runs.failure_explanation`

**Relevant transitions**:

```text
evaluating_relevance -> summarizing
summarizing -> assessing_coverage    when summary work set completed with usable summaries
summarizing -> failed                when no usable summaries exist or state conflicts
```

**Validation rules**:

- The summary work set informs the transition, but the unified research graph
  remains the writer of `research_runs.status`.
- A single failed execution cannot force `research_runs.status = failed` when
  the aggregate work set has usable completed summaries.
