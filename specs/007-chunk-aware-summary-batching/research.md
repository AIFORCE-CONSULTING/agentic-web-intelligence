# Research: Chunk-Aware Summary Batching

## Decision: Keep batching inside the evidence-summary service

**Rationale**: LangGraph owns the high-level research workflow state: it decides
that eligible evidence needs summarization and waits for the summary stage to
finish. The exact number of sources placed into a Temporal execution is an
internal packaging decision for summary work. Keeping it in the evidence-summary
service preserves the current ownership boundary and avoids turning LangGraph
into a second summary batching engine.

**Alternatives considered**:

- Put batching logic in LangGraph. Rejected because the graph should not need to
  know whether one summary stage becomes one, two, or five Temporal executions.
- Let Temporal dynamically split work. Rejected because the platform already
  knows source chunk counts before scheduling and should avoid oversized jobs
  before they enter durable execution.

## Decision: Use chunk count as the primary work-size signal

**Rationale**: The observed bottleneck was caused by variation in source chunk
counts. Recent local data showed sources ranging from 1 to 23 chunks, with an
average near 5.56 chunks and approximately 22 seconds per chunk. Chunk count is
already produced by the deterministic chunking policy and directly predicts the
number of model calls needed for per-chunk summarization.

**Alternatives considered**:

- Use source count only. Rejected because it caused the observed timeout.
- Use character count only. Rejected because chunk count is closer to actual
  model-call count and already includes overlap behavior.
- Ask the model to estimate effort. Rejected because the model must not decide
  execution packaging or durable routing.

## Decision: Preserve a maximum source count and add a maximum chunk count

**Rationale**: Small sources should remain efficient. A five-source maximum is
reasonable when total chunk count is low. The initial chunk threshold rounds the
observed average of 5.56 chunks to 6 chunks: 1 to 5 chunks is small, 6 to 15
chunks is above-normal, and 16 or more chunks is oversized. A 15-chunk group
limit prevents a five-source group from becoming too large. A source that
exceeds that limit by itself must still be processable, so it is isolated rather
than rejected by batching.

**Alternatives considered**:

- Send every source separately. Rejected because it creates unnecessary overhead
  for small sources.
- Increase the Temporal timeout only. Rejected because it hides the batching
  problem and can still fail for unusually large groups.
- Lower the global source limit. Rejected because the operator should still be
  able to request broad research.

## Decision: Continue from aggregate work-set success

**Rationale**: The current work-set store already treats the aggregate as
completed when at least one internal execution completed. That matches the
desired business behavior: successful summaries should remain usable even when a
separate source fails. The durable workflow should use that aggregate status for
the graph continuation instead of letting the current execution's failure
automatically fail the research run.

**Alternatives considered**:

- Fail the research run whenever any execution fails. Rejected because it
  discards useful completed summaries and caused confusing operator outcomes.
- Ignore failed executions entirely. Rejected because operators still need clear
  failed-source records and failed sources must stay out of reports.

## Decision: Do not change chunk size in this feature

**Rationale**: The current chunking policy, `chunk-6000-overlap-500`, is
deterministic and already stored on source summary records. The immediate issue
is how many chunks are placed into one durable activity, not whether the chunk
size itself is correct. Changing chunk size would also alter summary quality and
prompt behavior, expanding the scope.

**Alternatives considered**:

- Reduce chunk size. Rejected for this feature because it would increase model
  calls and may worsen runtime.
- Increase chunk size. Rejected for this feature because it changes model input
  size and summary quality risks.

## Decision: No schema migration for first implementation

**Rationale**: The existing execution/source membership tables already record
which URLs belong to each execution, and `chunk_count` is stored per source once
prepared. Tests can verify grouping by inspecting execution membership and
source chunk counts. Avoiding a new table keeps this change focused.

**Alternatives considered**:

- Add a dedicated planner table. Rejected because it creates another durable
  record for information already represented by execution membership and source
  metadata.
