# Data Model: Completed Checkpoint Cleanup

## Existing Entities

### ResearchRun

Represents the operator-facing research workflow.

| Field | Meaning |
| --- | --- |
| `id` | Stable research task identity and LangGraph thread identity |
| `workspace_id` | Workspace that owns the run |
| `status` | Official operator-facing workflow state |
| `status_version` | Optimistic version for guarded transitions |
| `failed_stage`, `failure_code`, `failure_explanation`, `retryable` | Safe failure details when the official workflow fails |
| `updated_at` | Ordering signal for bounded cleanup retry candidates |

**State rule**: Cleanup never changes `status`. A run that is completed remains
completed even if cleanup fails.

### LangGraph Execution Bookmark

Represents framework-owned resumable graph state for a research run.

| Attribute | Meaning |
| --- | --- |
| `thread_id` | Research run id |
| `checkpoint_ns` | Workflow namespace, currently `unified-research:v1` |
| checkpoint rows/writes/blobs | Framework-owned execution data |

**State rule**: Active, waiting, failed, or review-required runs retain
bookmarks. Completed runs become cleanup-eligible after the official completed
transition and terminal graph return.

### ResearchCheckpointCleanup

Represents the audit outcome for one cleanup attempt.

| Field | Meaning |
| --- | --- |
| `research_run_id` | Completed run whose execution bookmarks were targeted |
| `outcome` | `succeeded` or `failed` |
| `explanation` | Safe explanation for failure, if any |
| `occurred_at` | Time of the audit event |

**State rule**: A run is absent from cleanup backlog when it has at least one
`succeeded` cleanup audit. Failed attempts remain visible and retryable.

### CleanupBacklog

Derived maintenance view of completed runs without a successful cleanup audit.

| Value | Meaning |
| --- | --- |
| `0` | No completed-run cleanup is pending |
| `>0` | Maintenance cleanup is pending or previously failed |

**State rule**: Backlog is health/maintenance information. It is not research
workflow status and does not block unrelated new research.

## State Transitions

### Research Run Status

Existing research workflow transitions remain unchanged. This feature observes
the existing `reporting -> completed` transition and then attempts cleanup.

### Cleanup Audit Outcome

```text
no cleanup audit
  -> failed
  -> succeeded

failed
  -> failed
  -> succeeded

succeeded
  -> succeeded (optional later idempotent audit, not required)
```

## Validation Rules

- Cleanup candidates must be completed research runs.
- Cleanup must not target active, waiting, failed, or review-required runs.
- Cleanup success must be recorded only after the framework deletion operation
  returns without error.
- Cleanup failure must record a safe explanation and must not modify research
  outputs or official research status.
- Backlog calculations must count completed runs lacking successful cleanup,
  but that count is not a blocker for unrelated research starts.
