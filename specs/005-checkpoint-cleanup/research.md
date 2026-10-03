# Research: Completed Checkpoint Cleanup

## Decision: Extend the Existing Checkpoint Lifecycle Owner

**Decision**: Use the existing `ResearchCheckpointLifecycle` as the sole owner
for checkpoint cleanup behavior.

**Rationale**: The current architecture already assigns LangGraph checkpoint
setup, readiness, deletion, retry, and maintenance commands to this component.
Creating a separate cleanup service would duplicate ownership and violate the
constitution's "one owner" rule.

**Alternatives considered**:

- Add a background cleanup worker: rejected because this would introduce
  another execution path for the same responsibility.
- Let API routes delete checkpoints directly: rejected because routes should
  start/resume research and should not own checkpoint lifecycle details.

## Decision: Use the Official Checkpointer Delete Operation

**Decision**: Cleanup must continue to use the official LangGraph checkpointer
thread-deletion operation exposed through the saver abstraction.

**Rationale**: Checkpoint data spans multiple framework-owned tables. The
existing implementation already abstracts cleanup through the official saver
instead of issuing direct SQL against framework tables. That preserves framework
consistency and keeps the application out of LangGraph's table internals.

**Alternatives considered**:

- Delete rows directly from checkpoint tables: rejected as unsafe because it
  couples application code to framework-owned storage internals.
- Leave checkpoints forever: rejected because completed runs no longer need
  resumable execution bookmarks and this would bloat the database.

## Decision: Cleanup Backlog Is Maintenance Health, Not Research Readiness

**Decision**: Pending cleanup for completed runs should degrade maintenance
health but should not block unrelated new research starts.

**Rationale**: A completed run's checkpoint is no longer needed to decide
whether a different research task may begin. Blocking new research makes
maintenance backlog feel like a user-facing failure even though completed
research outputs are safe.

**Alternatives considered**:

- Keep blocking readiness until backlog is zero: rejected because the observed
  behavior prevented a second search after a successful first run.
- Hide backlog entirely: rejected because operations still need visibility into
  cleanup failures and pending work.

## Decision: Cleanup Is Best-Effort After Completion Plus Bounded Retry

**Decision**: Attempt cleanup after the official completed transition and keep
the existing bounded maintenance retry path for failures or older pending runs.

**Rationale**: The completed research record must be committed before cleanup is
attempted. Cleanup failure should not reverse the completed business outcome.
Bounded retry prevents unbounded startup or operator-triggered maintenance work.

**Alternatives considered**:

- Cleanup before marking the run completed: rejected because a cleanup failure
  would incorrectly hold a finished research task open.
- Unbounded retry until success: rejected because an unavailable checkpoint
  dependency could stall the platform.

## Decision: No Model, Human Approval, MCP, or Temporal Change

**Decision**: This feature does not change model behavior, human trust-review
decisions, MCP capabilities, or Temporal durable execution.

**Rationale**: Cleanup is local workflow maintenance. It should not affect
trust policy, evidence eligibility, model context, or durable background work.

**Alternatives considered**:

- Add an operator approval before cleanup: rejected because completed-run
  execution bookmarks are maintenance-only and do not contain the canonical
  research result.
- Make cleanup a Temporal workflow: rejected for this slice because cleanup is
  bounded, local, best-effort maintenance and has an existing retry command.
