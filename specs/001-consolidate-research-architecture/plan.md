# Implementation Plan: Consolidated Research Architecture

**Branch**: `001-consolidate-research-architecture` | **Date**: 2026-09-26 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/001-consolidate-research-architecture/spec.md`

## Summary

Replace the three overlapping research-control paths with one governed path
started by the existing **Discover Sources** action. The existing topic-driven
LangGraph becomes the sole research coordinator. `RuntimeService` authorizes
every model-proposed capability from stored assignments and limits. The
governed MCP host remains the only agent-facing web-tool boundary.
`EvidenceTrustService` and the evidence-review service retain evidence
eligibility and human-decision authority. Existing direct-versus-Temporal
routing remains deterministic. The official LangGraph PostgreSQL checkpointer
provides resumable graph execution, while the existing application stores in
PostgreSQL remain the official business and audit record.

The route-level sequence, `AgenticResearchControlService`, the plain-Python
research router, the old first-result LangGraph executor, and
`GovernedRuntimeWorkflow` are retired only after callers and tests use the
consolidated path.

## Technical Context

**Language/Version**: Python 3.12 API and workers; TypeScript 5.8 / React 19 operator UI  
**Primary Dependencies**: FastAPI 0.136, LangGraph 1.2, official LangGraph PostgreSQL checkpointer, Temporal Python SDK 1.32, Pydantic 2.13, existing governed MCP host, Ollama 0.6 client boundary  
**Storage**: PostgreSQL through `ResearchStore`, `RuntimeStore`, `WebTrustStore`, `EvidenceSummaryStore`, and `AgenticResearchStore`; LangGraph checkpoint tables hold execution snapshots only  
**Testing**: pytest 9 for unit, contract, integration, Temporal, and end-to-end tests; Ruff; TypeScript compiler and Vite production build  
**Target Platform**: Local Docker Compose services with native local Ollama; FastAPI and Temporal workers on Python 3.12  
**Project Type**: Local-first web application with API, React UI, MCP tool host, PostgreSQL, and Temporal worker  
**Performance Goals**: Preserve the current operator interaction and source limits; do not add an extra approval screen; direct work returns stored status promptly while durable work continues asynchronously  
**Constraints**: Local-first, modest hardware, default deny, no model authority, no raw browser/shell/database/network access, at most 50 sources per task, at most 3 planned topics, at most 2 missing-topic rounds  
**Scale/Scope**: One workspace-scoped research task per normalized question, up to 50 candidates, bounded local-model context, and one resumable graph thread per research task

## Constitution Check

*GATE: Passed. C1 state ownership, C2 checkpoint lifecycle, and C3
dependency-failure behavior are resolved and re-checked. Explicit architecture
approval was recorded on 2026-09-26, so implementation may proceed through the
approved tasks and checkpoints.*

### Canonical owners

| Responsibility | Existing owner and evidence | Target treatment |
| --- | --- | --- |
| Operator entry | `POST /v1/research/runs` in `apps/api/app/main.py`; ADR 0004 | Keep as a thin authenticated entry route. It validates the request and delegates to the unified graph entry adapter, which creates or reuses the research task and assignment, records the operator's start decision, and starts or resumes the graph. |
| Research coordination | Inline route sequence, `ResearchOrchestrationService`, old runtime graphs, and `build_research_workflow`; constitution Principle III | Keep only `build_research_workflow` as the canonical LangGraph. Transfer useful bounded transitions from the plain-Python router and remove duplicate coordinators. |
| Agent authority | `RuntimeService` plus overlapping `AgenticResearchControlService`; ADRs 0005, 0013, 0016 | Extend `RuntimeService` and `RuntimeStore`; move query reservation, source-attempt, source-scope, stage, and gap-limit checks under this owner. Retire `AgenticResearchControlService`. |
| Agent-visible tools | `GovernedWebMcpHost` and code-owned registry; ADRs 0004 and 0010 | Reuse. Graph nodes submit authorized `web.search` and `web.extract` calls through the in-process governed MCP boundary, not directly to providers. |
| Evidence eligibility | `EvidenceTrustService` and `WebTrustStore`; ADR 0015 | Reuse unchanged as the sole trust-policy owner. Runtime authorization consumes only bounded stored trust facts. |
| Human evidence acceptance | Evidence trust acceptance route/service/store; ADR 0015 | Reuse unchanged. LangGraph may wait and resume, but cannot create or reinterpret the decision. |
| Summaries and keywords | `EvidenceSummaryService`, `EvidenceSummaryAutomation`, and store; ADR 0014 | Reuse. The graph requests summaries only for eligible, relevant stored evidence. |
| Durable execution | `CandidatePreflightWorkflow`, `EvidenceSummaryWorkflow`, Temporal worker; ADR 0013 | Preserve these workflows and add a typed completion activity that resumes the same LangGraph thread. Remove only `GovernedRuntimeWorkflow`. |
| Business and audit state | Existing PostgreSQL stores | Reuse. Add authority-policy and decision fields under `RuntimeStore`; keep graph checkpoints separate from business records. |

### State and Decision Ownership Matrix

| State or decision | Business question | Canonical record and field | Authorized writer | Readers | Derived copies | Allowed transitions | Conflict resolution |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Research workflow status | What stage or final outcome has this research reached? | `research_runs.status`, `status_version`, `failed_stage`, `failure_code`, safe `failure_explanation`, `retryable`, and append-only research transition audit in `ResearchStore` | The unified LangGraph workflow, exclusively through guarded `ResearchStore` methods | Research API/UI, `RuntimeService`, graph nodes, recovery code, operational reads | LangGraph current-node/checkpoint data; Temporal wait metadata; runtime step status | The complete transition table below | Canonical research row wins. Stale writers make no change, append a conflict audit, reload, and resume or fail safely. |
| Agent action authority | May this proposed action execute now? | Runtime assignment, step, grants, counters, and persisted authorization decision in `RuntimeStore` | `RuntimeService` | Unified graph nodes, governed MCP host, audit/admin reads | Safe decision summaries in logs or UI | Allow or deny after reloading the current research status and runtime facts | Stored runtime facts and latest research status win; malformed, stale, or missing facts deny by default. |
| MCP execution audit | Which authorized request caused this tool call and what happened? | Existing MCP execution audit extended with research, runtime, step, authorization-decision, request, tool, resource, and outcome identities | Governed MCP host | Audit/admin reads and integration verification | Provider logs are operational only | One execution audit per governed invocation attempt | Missing or mismatched authorization correlation blocks provider invocation; stored authorization and MCP audit identities must agree. |
| Graph resume position | Where should LangGraph resume execution? | Official LangGraph PostgreSQL checkpoint for the research-task thread and graph namespace | LangGraph checkpointer as invoked by the unified workflow | Unified graph start/resume adapter | None; this is already a derived execution bookmark | Framework checkpoint progression and interrupts only | If it conflicts with research status, research status wins and bounded graph context is reconstructed from official stores. |
| Durable work progress | Is an acquisition or summary job queued, running, completed, or failed? | Existing candidate-preflight and evidence-summary execution records; Temporal history remains operational only | Existing durable-execution service and Temporal worker/activity boundaries | Admin durable-work read model and continuation activity | Temporal visibility data | Existing durable-work transitions; completion requests graph continuation | Owning application records win. The Admin view never translates Temporal state into business status. |
| Evidence trust eligibility | May this evidence enter automated processing? | Existing versioned trust evaluation and human acceptance records in `WebTrustStore` | `EvidenceTrustService` and the authenticated human-review path | Unified graph, summary and reporting services, operator review UI | Bounded eligibility facts used by `RuntimeService` | Existing trust-policy and human-decision transitions | Trust store wins; workflow, checkpoints, Temporal, and model output cannot reinterpret it. |

#### Research workflow transition table

`research_runs.status` uses exactly these values in the consolidated workflow:

| Current status | Permitted next status | Business meaning |
| --- | --- | --- |
| new record | `planning` | The unified workflow has accepted the operator request. |
| `planning` | `discovering`, `failed` | Topics are stored before discovery starts. |
| `discovering` | `acquiring`, `evaluating_relevance`, `assessing_coverage`, `failed` | New candidates, reusable evidence, or no usable candidates determine the next stage. |
| `acquiring` | `awaiting_review`, `evaluating_relevance`, `assessing_coverage`, `failed` | Captured evidence moves forward; review blocks the run only when no other work can proceed. |
| `awaiting_review` | `evaluating_relevance`, `assessing_coverage`, `failed` | A stored human outcome permits evidence use or leaves it excluded. |
| `evaluating_relevance` | `summarizing`, `assessing_coverage`, `failed` | Only eligible and relevant evidence proceeds to summarization. |
| `summarizing` | `assessing_coverage`, `failed` | Stored summaries and keywords become coverage inputs. |
| `assessing_coverage` | `discovering`, `reporting`, `failed` | At most two missing-topic rounds may return to discovery; otherwise reporting begins. |
| `reporting` | `completed`, `failed` | The stored grounded report precedes completion. |
| `failed` | the stored `failed_stage` only | An explicit retry revalidates records and resumes the failed stage. |
| `completed` | none | Completion is terminal. |

Each transition uses an expected status and `status_version`, and writes an
idempotent transition identity plus an append-only audit entry in the same
transaction. A route, `RuntimeService`, Temporal workflow/activity, worker, MCP
tool, or model response cannot write this status.

### No parallel authority

The plan creates no second workflow engine, policy authority, tool registry,
trust service, review service, or business store. The official LangGraph
checkpointer is execution infrastructure for the canonical graph, not a new
business source of truth. `AgenticResearchControlService` and the plain-Python
router are migration sources, not retained peers.

### Checkpoint lifecycle

- **Setup**: Application startup creates one `AsyncPostgresSaver` from the
  existing PostgreSQL configuration and calls its idempotent `setup()` before
  the research API becomes ready. Setup failure keeps research startup
  unavailable; the platform does not fall back to memory or another saver.
- **Serialization safety**: Enable LangGraph strict MessagePack handling or an
  explicit allowlist. Checkpoint state remains limited to approved typed graph
  values and identifiers; raw webpage content, credentials, and authority
  records remain excluded.
- **Thread and namespace**: `thread_id` is the research-task UUID.
  `checkpoint_ns` is `unified-research:v1`. Any future graph change that cannot
  safely interpret existing state increments this namespace and requires an
  explicit migration or clean-start decision before deployment.
- **Retention**: Keep checkpoint history while research is in any active stage,
  `awaiting_review`, or `failed`, because those runs can resume. Do not use a
  time-based retention rule for resumable work.
- **Terminal cleanup**: After the report and `completed` transition commit and
  after the terminal graph invocation returns, the graph runner adapter calls
  the official `adelete_thread(thread_id)` API. This ordering prevents the graph
  from writing another terminal checkpoint after cleanup. Deliberate deletion
  of a research task invokes the same cleanup. Checkpoint deletion never
  deletes or changes business records.
- **Cleanup failure**: A failed deletion does not reverse `completed`. Record a
  bounded `research.checkpoint_cleanup_failed` audit event. Startup retries the
  oldest 100 completed research IDs that lack a successful cleanup audit; an
  explicit maintenance command processes additional batches. Repeated cleanup
  is idempotent, and an outstanding backlog is visible as degraded readiness.
- **Obsolete checkpoints**: Before enabling `unified-research:v1`, stop API and
  worker processes. The local clean-start command uses the saver's paged
  `alist(None, ...)` result to collect distinct old thread IDs and calls
  `adelete_thread()` for each before rerunning `setup()`. It does not issue
  application-authored deletion SQL against framework tables. This repository
  does not require old graph execution history to remain readable. Future
  incompatible versions follow the namespace and migration rule above.

These rules use the official saver lifecycle rather than custom checkpoint
tables or SQL during normal operation. The official LangGraph PostgreSQL saver
requires explicit setup and provides thread deletion through
`adelete_thread()`.

### Dependency-unavailable behavior

No required dependency has an automatic substitute. The owning boundary
classifies the failure; the unified workflow alone changes research status.

| Unavailable dependency | Failure owner and immediate outcome | Official research outcome | Recovery |
| --- | --- | --- | --- |
| PostgreSQL, including checkpoint setup | Database/checkpointer adapter fails readiness. API returns service unavailable and RuntimeService denies execution because it cannot load or store authority. | No status write is attempted; the last committed `research_runs` row remains official. | Restore PostgreSQL, pass readiness, reload all official records, then accept start or retry. No memory fallback is permitted. |
| Temporal | Durable-execution service fails mandatory readiness, so new research starts are unavailable. An outage during scheduling or continuation returns a typed retryable error. | After Temporal's configured retries are exhausted, the unified workflow writes `failed`, the current `failed_stage`, and `temporal_unavailable`. | After Temporal readiness succeeds, the operator uses the existing Discover action to resume the failed stage. Qualifying work is never rerouted to direct execution. |
| MCP search provider | Governed MCP host returns provider-unavailable rather than a fabricated empty result. | After the stored application retry limit is exhausted, the workflow writes `failed`, `discovering`, and `search_unavailable`. | Restore provider readiness and resume from `discovering`; prior queries and sources remain reusable. |
| MCP extraction provider | Governed MCP host returns provider-unavailable separately from source-level unreachable outcomes. | After the stored application retry limit is exhausted, the workflow writes `failed`, `acquiring`, and `extraction_unavailable`. It does not mark every source unreachable. | Restore provider readiness and resume from `acquiring`; completed evidence is reused. |
| Local Ollama model | The topic, relevance, summary, coverage, or reporting service returns model-unavailable; missing output is never accepted. | After the stored application retry limit is exhausted, the workflow writes `failed`, the current stage, and `model_unavailable`. | Restore the approved local model and resume the failed stage. No cloud-model fallback is permitted. |

Every persisted failure includes dependency class, stable code, failed stage,
retryability, occurrence time, and a safe explanation. It excludes credentials,
connection strings, raw model responses, and provider secrets. Readiness
reports the unavailable dependency directly; it does not rewrite every active
research run merely because a shared dependency is temporarily down.

### Durable-work operator view

- Keep the Admin **Durable work** location so operators do not need a second
  console, but replace its old runtime-workflow data source.
- Add one read-only, workspace-scoped research endpoint that reads the research
  task plus existing candidate-preflight and evidence-summary execution records
  through their owning stores. Runtime assignment details are not part of this
  operator view.
- Show the research question and run ID, durable operation type, selected route
  (`direct` or `temporal`), stored operation status, last update, and bounded
  failure code or explanation.
- Read status from the owning PostgreSQL records. Temporal history may help
  operators diagnose infrastructure separately, but it is not translated into
  the application status shown here.
- Do not copy durable-work state into another table. The endpoint is a composed
  read model only.
- Consolidated research entries are inspectable but not cancellable or
  approvable from this section. Evidence acceptance remains in the existing
  evidence-review workflow.
- Preserve administrator/operator authorization and workspace isolation.
- Retire `/v1/runtime/runs` and its approval, attention, and cancellation
  controls with `GovernedRuntimeWorkflow`. Delete the obsolete local runtime
  and durable test records during the approved clean start. No compatibility
  adapter, data migration, or legacy display is required.

### Selected foundations

- **LangGraph** coordinates every research stage and uses its official async
  PostgreSQL checkpointer with the research task ID as the stable thread ID.
- **RuntimeService** reloads stored workspace, assignment, step, the canonical
  `research_runs.status`, resource, grant, policy version, and counters for each
  capability decision.
- **MCP** remains the web-tool boundary. Authorized graph nodes use the existing
  code-owned registry and governed host; they do not call SearXNG or extraction
  providers directly.
- **Temporal** runs only pre-existing, validated acquisition or summary work
  selected by deterministic thresholds. A completion activity resumes the
  persisted graph thread.
- **PostgreSQL** stores all research, runtime, trust, review, evidence, summary,
  coverage, report, decision, and audit records. Checkpoints contain bounded
  execution state and identifiers.

### Model boundary

The model may propose topics, relevance, and approved research capability
requests. Pydantic contracts and deterministic code validate every response.
Stored runtime assignments grant capabilities. Evidence acceptance remains
human-only. The model cannot grant authority, change policy or limits, select
direct versus durable execution, write arbitrary records, call Temporal, or
access providers, MCP transport, PostgreSQL, credentials, files, browser, shell,
or network directly.

### Migration and retirement

- Retain active research, evidence, trust, review, summary, topic, relevance,
  coverage, and report records because they remain useful product data and test
  fixtures.
- A clean local reset is permitted for old general-runtime runs, old capability
  audit/control records, obsolete graph checkpoints, and obsolete Temporal
  runtime histories. No compatibility adapter is required for these records.
- Move all production callers before deleting old code. Transfer useful tests
  to `RuntimeService` and the unified graph before removing their old subjects.
- Remove the old executor and `GovernedRuntimeWorkflow` registration only after
  repository-wide caller checks and end-to-end tests show zero active callers.

### Operational checkpoint

- **Trigger**: An authenticated operator enters a question, chooses a total
  source count, and selects **Discover Sources**.
- **Authority**: `RuntimeService`, using its versioned stored policy and
  assignment, decides whether proposed actions may execute. It reads but never
  writes the research workflow status.
- **Research state transitions**: The unified LangGraph workflow is the sole
  initiator of guarded `research_runs.status` transitions through
  `ResearchStore`. The authenticated Discover action records human intent but
  cannot advance workflow status itself.
- **Canonical state**: `research_runs.status` is the operator-facing research
  status. The UI and `RuntimeService` read it. LangGraph checkpoints contain
  only resumable execution position and bounded context. Temporal records
  contain only durable-work progress.
- **Direct or durable**: Existing service-owned deterministic thresholds select
  direct execution or Temporal. Neither operator nor model selects it.
- **Human decisions**: Evidence acceptance remains an attributed, scoped,
  expiring record in `WebTrustStore`, independent of LangGraph and Temporal.
- **Excluded callers and capabilities**: No model, MCP client, browser, old
  graph, route helper, or Temporal workflow may grant authority or start a
  separate research path. Cookie handling, browser control, shell, file access,
  credentials, and new tools remain out of scope.

### Approval status

Approved by the user on 2026-09-26 after review of the final architecture
checkpoint, including canonical research-state ownership, RuntimeService
authority, LangGraph checkpoint lifecycle, mandatory Temporal behavior,
dependency failures, governed MCP access, evidence trust, human review, and
retirement of duplicate paths. Runtime implementation may proceed through the
approved tasks and checkpoints.

### Post-design re-check

C1 passes after ownership remediation. C2 passes after defining setup,
namespace versioning, resumable retention, terminal deletion, cleanup retry,
and obsolete-checkpoint handling. C3 passes after assigning every required
dependency failure to an owner, official outcome, safe operator response, and
recovery path without fallback substitution. The state matrix identifies the exact
research record, sole transition writer, readers, derived copies, complete
transitions, and conflict rules. The data model extends `RuntimeStore`;
contracts preserve existing operator and MCP boundaries; the official LangGraph
checkpointer solves graph resumption; Temporal remains subordinate; and every
retirement has a caller and test condition. Explicit architecture approval was
recorded on 2026-09-26. The Constitution Check passes with no exception.

## Project Structure

### Documentation (this feature)

```text
specs/001-consolidate-research-architecture/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── durable-work-api.md
│   ├── research-api.md
│   ├── runtime-authorization.md
│   └── workflow-continuation.md
└── tasks.md
```

### Source Code (repository root)

```text
apps/api/app/
├── main.py
├── agent_runtime/
│   ├── contracts.py
│   ├── policy.py
│   ├── service.py
│   ├── store.py
│   ├── research_workflow.py
│   └── workflow.py                 # Remove after migration
├── agentic_research/
│   ├── capabilities.py
│   ├── contracts.py
│   ├── workflow_nodes.py
│   ├── topic_planning.py
│   ├── relevance.py
│   ├── reporting.py
│   ├── store.py
│   ├── control.py                  # Remove after RuntimeService migration
│   └── orchestration.py            # Remove after graph test migration
├── web_research/
│   ├── mcp_host.py
│   ├── store.py
│   └── workflow.py
├── web_trust/
│   ├── preflight.py
│   ├── service.py
│   └── workflow.py
├── evidence_summaries/
│   ├── service.py
│   ├── store.py
│   └── workflow.py
└── durable_execution/
    ├── worker.py
    └── workflows.py                # Remove obsolete runtime workflow

apps/api/tests/
apps/web/src/App.tsx
docs/
ROADMAP.md
```

**Structure Decision**: Keep the existing web application and module boundaries.
Extend canonical owners in place. Do not create a new orchestration package,
authorization service, policy engine, database, MCP server, or worker type.

## Implementation Sequence

### 1. Strengthen the existing authority boundary

1. Add an explicit RuntimeService authority-policy version and stable decision
   reason codes.
2. Link one stored runtime assignment to one workspace-owned research task.
3. Replace object-based `authorize_capability(step, capability)` with a request
   containing stored run, step, research task, action, resource, stage, and
   bounded context identifiers.
4. Reload canonical records before deciding; do not accept caller-supplied
   roles, grants, trust outcomes, ownership, counters, or workflow stage.
5. Move query reservation, discovered-source scope, source-attempt limits,
   source limits, retry limits, and two-round gap limits from
   `AgenticResearchControlService` into `RuntimeService`/`RuntimeStore`.
6. Persist allow and deny decisions before execution with policy version,
   reason code, safe explanation, and redacted facts.
7. Require the governed MCP host to verify and persist workspace, research
   task, runtime run, runtime step, authorization decision, request, tool, and
   resource correlation for every agent-triggered invocation.
8. Add the complete default-deny authorization matrix before changing callers.

### 2. Make the unified LangGraph resumable and authoritative for sequence

1. Add one official `AsyncPostgresSaver`, enable strict MessagePack handling,
   and call its idempotent `setup()` during application startup before research
   readiness succeeds.
2. Compile one graph per application process, use the research task UUID as the
   stable `thread_id`, and use `unified-research:v1` as `checkpoint_ns`; never
   create a custom graph-state store.
3. Keep identifiers and bounded progress in graph state. Reload business facts
   through owning services at every consequential node.
4. Add guarded, versioned research-status transitions to `ResearchStore`; only
   unified graph nodes may invoke them. Treat the research row as authoritative
   whenever it disagrees with a checkpoint.
5. Change search and acquisition nodes to request RuntimeService authorization
   and invoke the existing governed MCP host after an allow decision.
6. Keep topic planning, trust, relevance, summary, coverage, reporting, and
   completion with their current service owners.
7. Replace terminal placeholder wait nodes with standard LangGraph interrupts
   for human review and durable work.
8. Retain checkpoints for active, waiting, and failed runs. After completed
   business state commits, delete that thread with `adelete_thread()`. Audit and
   retry cleanup failures without changing the completed result.

### 3. Connect Temporal completion to the same graph thread

1. Extend existing preflight and summary workflow envelopes with stable
   research task, graph thread, and expected resume-stage identifiers.
2. After the durable activity stores its result, execute one typed continuation
   activity that reloads canonical state and resumes the graph using LangGraph's
   standard resume command.
3. Make continuation idempotent by checking stored stage, execution identity,
   and completed result before resuming.
4. Require the resumed graph to compare the expected research status and
   `status_version`; Temporal never advances `research_runs.status` directly.
5. Preserve `CandidatePreflightWorkflow` and `EvidenceSummaryWorkflow`; do not
   combine them into a generic workflow.
6. Keep Temporal workflow code deterministic. Database, model, MCP, and graph
   calls occur only in activities.

### 4. Connect the existing operator action

1. Refactor `POST /v1/research/runs` to authenticate and validate, then call the
   unified graph entry adapter. The adapter finds or creates the canonical
   research task through `ResearchStore`, creates or reuses its RuntimeService
   assignment, records the authenticated start decision, starts or resumes the
   graph, and returns `research_runs.status`.
2. Remove search, source save, preflight routing, and summary routing from the
   route body.
3. Preserve the request and response shapes, 200/201 reuse behavior, source
   count choices, and existing UI polling.
4. Resume a graph waiting for human evidence review after the existing review
   service has stored a valid decision; do not move review authority into the
   graph.
5. Keep the UI and polling API on `research_runs.status`; do not translate
   checkpoint nodes, runtime-step status, or Temporal state into research
   status.

### 5. Retire overlap after caller migration

1. Remove `AgenticResearchControlService` after its stored checks, audits, and
   tests are owned by RuntimeService.
2. Remove `ResearchOrchestrationService` after its useful routing cases exist in
   canonical graph tests.
3. Remove old deterministic planning, first-result execution, reviewer-cycle,
   and scheduling code after all callers are gone.
4. Remove `GovernedRuntimeWorkflow`, its service boundary, worker registration,
   tests, application startup dependencies, and old `/v1/runtime/runs` list,
   detail, approval, attention, and durable-cancellation routes after the
   replacement research durable-work endpoints and Admin UI are verified.
5. Keep RuntimeService, RuntimeStore, the Admin durable-work read experience,
   active preflight/summary workflows, and offline model evaluation.

### 6. Verify and document the consolidated system

1. Run contract, authorization, graph, service, Temporal, API, and UI tests.
2. Prove limits, URL reuse, direct and durable work, trust exclusion, malformed
   response handling, two gap rounds, idempotent retry/resume, human review, and
   report grounding.
3. Perform a repository-wide caller audit for retired classes and workflows.
4. Update ADR 0016, the architecture diagram, glossary, runtime documentation,
   caller descriptions, and Phase 7.5 roadmap status to match running code.

## Complexity Tracking

No constitutional violations or new architectural authorities are proposed.
The LangGraph PostgreSQL checkpointer is an official framework component used
only for execution checkpoints; it does not replace application stores or
create a new business source of truth.
