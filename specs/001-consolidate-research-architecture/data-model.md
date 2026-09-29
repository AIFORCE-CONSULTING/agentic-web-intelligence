# Data Model: Consolidated Research Architecture

PostgreSQL remains the official business and audit record. Existing stores keep
their domains. LangGraph checkpoint tables store framework execution snapshots,
not business authority.

## Retained entities

### Research Task

Retain `research_runs`, target keys, sources, evidence, and audits under
`ResearchStore`. One normalized workspace question has one research task, many
candidate/evidence records, up to three topics, and at most one active runtime
assignment. `research_runs.status` is the official operator-facing workflow
status and is read by both the UI and `RuntimeService`.

Add or formalize these research-run fields:

| Field | Rule |
| --- | --- |
| `status` | One of `planning`, `discovering`, `acquiring`, `awaiting_review`, `evaluating_relevance`, `summarizing`, `assessing_coverage`, `reporting`, `completed`, or `failed`. |
| `status_version` | Monotonically increasing integer used for guarded transitions. |
| `failed_stage` | The non-terminal stage where failure occurred; required only when status is `failed`. |
| `workflow_version` | The unified graph contract that produced the status. |
| `failure_code` | Stable typed code such as `temporal_unavailable`, `search_unavailable`, `extraction_unavailable`, or `model_unavailable`; set only for failed work. |
| `failure_explanation` | Safe operator-facing explanation without secrets or raw provider/model output. |
| `retryable` | Whether the existing Discover action may retry after readiness is restored. |
| `failed_at` | Time the current failure was committed. |

Research transition audits record the prior status, next status, prior and new
status version, workflow version, idempotent transition identity, reason, and
time. Only the unified workflow may request these guarded writes through
`ResearchStore`.

PostgreSQL unavailability is the one dependency failure that cannot create a
new failure record. The last committed row remains official until PostgreSQL
returns. No cache, checkpoint, Temporal history, or in-memory object replaces
it.

### Semantic research records

Retain topics, relevance decisions, coverage evidence, topic/source
associations, and reports under `AgenticResearchStore`. Remove control, limit,
and authorization methods from that store after RuntimeStore owns them.

### Trust, review, and summaries

Retain existing policy, evaluation, override, summary execution, chunk,
consolidation, and artifact records under their current stores. RuntimeService
may consume bounded facts but cannot write or reinterpret these decisions.

## Runtime authority entities

### Runtime Run / Agent Assignment

Extend `agent_runtime_runs` with:

| Field | Rule |
| --- | --- |
| `research_run_id` | Unique foreign key to `research_runs`; one assignment per research task. |
| `authority_policy_version` | Required server-owned policy version for new records. |

Existing ID, workspace, goal, status, and timestamps remain. The authenticated
Discover action creates or reuses this assignment; callers cannot select roles
or grants.

### Runtime Step

Retain the stored role, capabilities, attempt count, idempotency key, timeout,
and status. The workflow uses a server-created researcher step for initial
`web.search` and `web.extract` grants.

### Capability Request

A validated request includes workspace, runtime run and step, research task,
workflow stage, action, resource type and ID, bounded typed arguments,
request/idempotency ID, and purpose. It excludes caller-supplied role, grants,
trust outcome, human decision, and counters.

### Authorization Decision

Persist under `RuntimeStore` before tool execution:

| Field | Rule |
| --- | --- |
| `id` | UUID identity. |
| `workspace_id` | Stored workspace evaluated. |
| `runtime_run_id`, `runtime_step_id` | Stored assignment evaluated. |
| `research_run_id` | Research task scope. |
| `action` | Known capability. |
| `resource_type`, `resource_id` | Bounded target identity. |
| `decision` | `allow` or `deny`. |
| `reason_code` | Stable testable reason. |
| `explanation` | Safe operator-facing text. |
| `authority_policy_version` | Exact rules used. |
| `request_facts` | Redacted JSON without content or secrets. |
| `created_at` | Decision time. |

Minimum reasons: `allowed`, `unknown_action`, `run_inactive`, `step_inactive`,
`capability_not_granted`, `wrong_workspace`, `wrong_research_task`,
`invalid_stage`, `resource_out_of_scope`, `source_not_discovered`,
`source_limit_exhausted`, `attempt_limit_exhausted`, `retry_limit_exhausted`,
`gap_limit_exhausted`, `human_decision_missing`, and `malformed_context`.

### MCP Execution Audit Correlation

Extend the existing MCP execution audit rather than creating another audit
store. Agent-triggered rows require:

| Field | Rule |
| --- | --- |
| `workspace_id` | Must equal the stored authorization workspace. |
| `research_run_id` | Must equal the authorized research task. |
| `runtime_run_id`, `runtime_step_id` | Must equal the assignment and step evaluated by RuntimeService. |
| `authorization_decision_id` | Required reference to the exact persisted allow decision. |
| `request_id` | Must equal the authorized idempotent request identity. |
| `tool_name` | Must correspond to the authorized action. |
| `resource_type`, `resource_id` | Bounded target identity; must match the decision when applicable. |
| `outcome` | Normalized `succeeded`, `failed`, or `denied`. |
| `occurred_at` | Execution-audit time. |

The governed MCP host validates the correlation before provider invocation and
writes the normalized outcome afterward. The audit excludes credentials,
secrets, raw webpage content, and unredacted model output. Existing non-agent
calls retain human or platform attribution and leave agent-only references
empty; they cannot supply an authorization decision identity.

### Reservations and counters

Move ownership of normalized query reservations, task/topic/source attempt
counts, and the 0–2 gap-search counter to `RuntimeStore`. Physical tables may be
retained during migration, but `AgenticResearchControlService` cannot remain a
second owner. Enforce limits transactionally before an allow decision.

## Graph and durable execution entities

### LangGraph Thread

- Thread ID: research task UUID.
- Namespace: versioned unified research graph.
- Contents: bounded graph state, current node, interrupt payload, framework
  metadata.
- Excludes: credentials, raw page bodies, model-asserted authority, and
  duplicate business records.
- Authority rule: the checkpoint never determines operator-facing research
  status. On disagreement, `research_runs.status` wins and the graph rebuilds
  bounded context from official stores.

#### Lifecycle

| Lifecycle concern | Decision |
| --- | --- |
| Setup | Application startup calls the official async saver `setup()` before research readiness succeeds. No in-memory fallback is permitted. |
| Serializer | Strict MessagePack mode or an explicit module allowlist is required. |
| Thread identity | Research-task UUID. |
| Namespace | `unified-research:v1`; incompatible graph state requires a new namespace. |
| Active retention | Retain full framework history while the research status is active, `awaiting_review`, or `failed`. |
| Completion | After report storage, the `completed` transition commit, and return from the terminal graph invocation, the graph runner calls `adelete_thread(thread_id)`. |
| Research deletion | Delete the checkpoint thread through the same official API. |
| Cleanup failure | Preserve the business outcome, append `research.checkpoint_cleanup_failed`, retry the oldest 100 uncleaned completed research IDs at startup, expose a remaining backlog as degraded readiness, and permit the same bounded batch through an explicit maintenance command. |
| Obsolete local state | During the approved one-time clean start, stop API/workers, enumerate distinct thread IDs through paged `alist(None, ...)`, delete each with `adelete_thread()`, and run `setup()` before accepting research. |

The normal runtime never edits framework checkpoint tables directly. A future
incompatible graph must either migrate active checkpoint state deliberately or
start a new namespace after an explicitly approved clean start; it cannot
silently read the old namespace.

### Durable Continuation

The existing Temporal workflow envelope adds research task, workspace, graph
thread and namespace, durable execution identity, expected wait/resume stage,
and idempotency identity. A completion activity verifies the stored result and
current checkpoint before issuing a standard LangGraph resume command.
The envelope carries expected research status and `status_version`. Temporal
may request continuation but cannot update research status.

## State transitions

1. The unified graph entry creates or reuses the Research Task through
   `ResearchStore`, establishes `planning`, and creates or reuses the Runtime
   Assignment.
2. RuntimeService records action-authority decisions but never writes research
   status.
3. LangGraph coordinates and writes guarded transitions through the exact
   transition table in `plan.md`.
4. Every web action receives a stored decision before MCP execution.
5. Direct work returns immediately; durable work interrupts and later requests
   continuation of the same graph thread without changing research status.
6. Review-required evidence is excluded while other work continues. The run
   enters `awaiting_review` only when no other workflow work can proceed and a
   human decision could change the outcome.
7. Final report storage precedes `reporting` to `completed`.
8. Any non-terminal stage may transition to `failed`; retry may return only to
   the stored `failed_stage` after official records are revalidated.

## Historical data

| Record group | Treatment |
| --- | --- |
| Research, evidence, trust, review, summaries, topics, relevance, coverage, reports | Retain and use as fixtures where helpful. |
| Old general-runtime records | Clean reset permitted; keep only purpose-built fixtures. |
| Old control/audit/reservation/attempt records | Clean reset permitted before RuntimeStore ownership. |
| Old LangGraph checkpoints | One-time stopped-process cleanup through official `alist` and `adelete_thread` APIs, followed by `setup()` for `unified-research:v1`. |
| Obsolete runtime Temporal history | Local reset permitted; no compatibility layer. |
