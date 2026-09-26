# Contract: Workflow Wait and Continuation

One LangGraph thread exists per research task, using the task UUID as thread ID.
The official PostgreSQL checkpointer stores execution snapshots; application
stores remain business authority.

For durable work, the graph interrupts with durable execution ID, wait type,
expected resume stage, task ID, and workspace ID. The Temporal envelope carries
these stable IDs plus namespace/version and idempotency information, never
credentials, raw evidence, or caller-provided authority.

After the durable activity stores its result, a continuation activity reloads
the task, execution, and checkpoint; verifies workspace, identity, status, and
wait reason; no-ops after prior continuation; resumes the same thread; and
records the outcome. Database, model, MCP, and graph calls occur in activities,
not deterministic workflow code.

The continuation envelope includes the expected `research_runs.status` and
`status_version`. Temporal never updates either field. The resumed unified
workflow compares those expected values with `ResearchStore` before proceeding:

- a matching completion resumes the same graph thread;
- a repeated completion returns the previously recorded continuation result;
- a late completion or status/version mismatch records a conflict and makes no
  research-status change;
- a missing or wrong-workspace task fails closed and records no transition;
- a stale checkpoint is not trusted to restore research status; bounded graph
  context is reconstructed from official stores;
- a durable-work failure allows the unified workflow to move the current
  non-terminal research status to `failed` and store that stage as
  `failed_stage`; and
- after process or worker restart, the same identities and expected version are
  used, so continuation remains idempotent.

If Temporal is unavailable before a durable workflow is accepted, scheduling
returns `temporal_unavailable`; qualifying work is not executed directly. If
Temporal exhausts its configured retries after accepting work, its persisted
failure result requests one continuation. The resumed unified graph records the
failed research stage and code. If PostgreSQL is unavailable, the continuation
cannot verify or write official state and fails for Temporal to retry; it never
uses checkpoint or workflow history as replacement business state.

For human review, the existing review service stores the decision first.
Trusted application code verifies the exact evidence version and resumes the
same thread. A resume command is not itself evidence approval.
