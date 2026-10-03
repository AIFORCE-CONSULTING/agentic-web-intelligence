# Contract: Completed Checkpoint Cleanup

## Operator Research Start Contract

### Scenario

An operator starts a new research task while a prior completed run has pending
checkpoint cleanup.

### Expected Behavior

- The new research request is accepted if all non-maintenance dependencies are
  ready.
- Pending completed-run cleanup does not produce the blocking message:
  `Completed research checkpoint cleanup is pending.`
- The prior completed run remains completed.
- The pending cleanup remains visible through maintenance health or audit views.

### Failure Behavior

- If checkpoint persistence itself is unavailable for active workflow
  checkpointing, research start may still fail safely.
- If only completed-run cleanup backlog exists, research start must not fail
  solely because of that backlog.

## Cleanup Attempt Contract

### Trigger

- A research run reaches completed status; or
- The bounded maintenance retry command/process requests cleanup for completed
  runs without successful cleanup audit records.

### Expected Behavior

- Only the completed run's execution bookmarks are targeted.
- Completed research outputs remain unchanged.
- A cleanup audit record is written with `succeeded` or `failed`.

### Failure Behavior

- Cleanup failure records `failed` with a safe explanation.
- The completed research run remains completed.
- A future retry may record `succeeded`.

## Health Contract

### Expected Behavior

- Health/readiness distinguishes checkpoint infrastructure availability from
  completed-run cleanup backlog.
- Completed-run cleanup backlog appears as degraded maintenance information.
- Completed-run cleanup backlog uses plain operator-facing wording that says
  cleanup affects only execution bookmarks and does not delete completed
  research outputs.
- Completed-run cleanup backlog alone does not mark the research workflow
  unable to start unrelated new research.
- Checkpoint infrastructure unavailability may still make new workflow
  execution unavailable because active research needs checkpoint persistence.

## Exclusions

- No new operator button is introduced.
- No model, MCP, trust-policy, evidence-review, summary, keyword, or report
  decision is changed.
- No direct SQL deletion of framework checkpoint rows is permitted.
