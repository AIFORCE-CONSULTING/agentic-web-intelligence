# Implementation Plan: Database Bootstrap Before Runtime

**Branch**: `010-database-bootstrap` | **Date**: 2026-10-04 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/010-database-bootstrap/spec.md`

## Summary

Move database schema setup out of lazy store initialization and into a dedicated
Docker-started database bootstrap step that completes before API routes and
durable worker activities accept research work. Runtime stores will open
database connections only after schema readiness has been established, and they
will no longer create, alter, drop, or repair schema while handling user
actions, LangGraph nodes, Temporal activities, model calls, trust decisions,
summaries, or reports.

The first implementation keeps the existing schema fragments owned by the
current stores, but changes when and who may run them. A single database
bootstrap command runs the fragments in a short-lived Docker startup service
before runtime work. API and worker startup then verify the schema bootstrap
result and fail readiness clearly if the database is missing, incompatible, or
unavailable.

## Technical Context

**Language/Version**: Python 3.12 API and durable worker; small TypeScript/React UI update for the ready/not-ready indicator  
**Primary Dependencies**: FastAPI, asyncpg, PostgreSQL 16, Temporal Python SDK, LangGraph PostgreSQL checkpointer, existing store classes  
**Storage**: PostgreSQL through existing service stores; LangGraph checkpoint tables remain execution bookmarks  
**Testing**: pytest for API/unit/integration tests; Docker Compose validation for local runtime behavior; Ruff for Python linting  
**Target Platform**: Local Docker Compose platform with API, durable worker, Postgres, Temporal, SearXNG, docs, and web UI  
**Project Type**: Local-first web application with API, worker, MCP host, PostgreSQL, LangGraph, and Temporal  
**Performance Goals**: Docker startup may spend bounded time preparing schema, but runtime research work must not run schema DDL after the run begins  
**Constraints**: Preserve existing business data; no new workflow state machine; no model, MCP, trust-policy, or report-behavior change; local test database can still start empty  
**Scale/Scope**: Applies to all API and durable-worker database-backed stores currently using lazy `execute_schema_setup`

## Constitution Check

*GATE: Passed before Phase 0 research; re-checked after Phase 1 design.*

- **Canonical owner:** Existing business stores remain canonical for their own
  business records. A new database bootstrap boundary owns operational schema
  preparation/readiness only. It does not own research status, evidence,
  summaries, reports, trust decisions, RuntimeService authority, LangGraph
  checkpoints, or Temporal work.
- **State and decision ownership:** The matrix below identifies the exact
  business/operational decisions touched by this feature. Database bootstrap
  readiness is operational readiness, not business truth.
- **No parallel authority:** The plan does not add a second research workflow,
  state machine, policy implementation, MCP host, summary service, report
  service, or durable execution path. It moves schema setup timing from lazy
  store connection into one startup/bootstrap lifecycle.
- **Selected foundations:** LangGraph continues coordinating research.
  RuntimeService continues owning agent authority. Temporal continues durable
  preflight and summary work. PostgreSQL remains the official business/audit
  store. This feature does not make LangGraph or Temporal responsible for
  schema readiness.
- **Model boundary:** Models receive no schema capability. They cannot request,
  approve, run, validate, or bypass database initialization.
- **Migration and retirement:** Existing store `SCHEMA` fragments are reused
  initially. Lazy schema setup inside runtime store connection paths is retired
  after bootstrap/readiness tests prove API and worker startup run schema setup
  before accepting work.
- **Operational checkpoint:** Trigger is Docker startup through a dedicated
  short-lived database bootstrap service, or explicit local/test invocation of
  the same command. Authority owner is the database bootstrap boundary.
  Canonical operational state is the bootstrap readiness outcome. Runtime work
  is direct only after readiness passes; durable worker activities do not run
  schema setup. There is no human evidence decision. Agents, models, MCP tools,
  UI research actions, LangGraph nodes, and Temporal activities are excluded
  from schema authority.
- **Approval:** This plan documents the design checkpoint. Runtime code changes
  still require explicit user approval before implementation.

### Architecture Reconciliation

| Existing responsibility | Current code / ADR | Current owner | Planned owner | Reuse / extend / retire |
| --- | --- | --- | --- | --- |
| Store schema setup helper | `apps/api/app/persistence.py::execute_schema_setup` | Shared persistence helper | Database bootstrap boundary for schema setup; runtime stores for normal data access | Reuse the advisory-lock idea; change runtime stores so they no longer call DDL during first use |
| Research business records | `apps/api/app/web_research/store.py`; ADR 0016 consolidated implementation amendment | `ResearchStore` | Unchanged | Reuse unchanged for business writes; retire schema setup call from runtime pool creation |
| Runtime authority records | `apps/api/app/agent_runtime/store.py`; ADRs 0005, 0013, 0016 | `RuntimeStore`/`RuntimeService` | Unchanged | Reuse unchanged for authority decisions; no schema authority granted to models or graph |
| Evidence trust records | `apps/api/app/web_trust/store.py`; ADR 0015 | `WebTrustStore`/`EvidenceTrustService` | Unchanged | Reuse unchanged for trust decisions; remove lazy schema setup path |
| Summary work/artifacts | `apps/api/app/evidence_summaries/store.py`; ADR 0014 | `EvidenceSummaryStore`/summary service | Unchanged | Reuse unchanged for summary records; worker activities must not run schema setup |
| Topic/relevance/report records | `apps/api/app/agentic_research/store.py`; ADR 0016 | `AgenticResearchStore` | Unchanged | Reuse unchanged for topic and report records; bootstrap creates/updates required columns first |
| Identity and audit records | `apps/api/app/identity/store.py`, `apps/api/app/identity/audit.py`; ADRs 0008, 0011 | Identity and audit stores | Unchanged | Reuse unchanged for auth/audit; bootstrap handles schema before admin/API operations |
| Local model provider config | `apps/api/app/local_models/store.py`; ADR 0014 | `LocalModelProviderStore` | Unchanged | Reuse unchanged for provider config; readiness distinguishes provider issues from database setup |
| API startup/readiness | `apps/api/app/main.py::create_app`, `/health/ready`, `/health/services` | FastAPI application startup/readiness | FastAPI startup verifies bootstrap readiness; health reports database initialization state | Extend readiness; do not make research routes initialize schema |
| Durable worker startup/activities | `apps/api/app/durable_execution/worker.py` | Temporal worker module | Worker startup verifies bootstrap readiness before polling work | Extend startup; retire activity-time schema setup |
| Local Compose ordering | `compose.yaml` | Docker Compose service dependency graph | Dedicated `database-bootstrap` service runs the bootstrap command after Postgres health and before API/worker readiness | Extend Compose with a short-lived bootstrap service; no separate business workflow |
| Operator readiness display | `apps/web/src/App.tsx` and API health responses | API health and React UI | UI reads API readiness and displays ready/not-ready state | Extend existing UI status display; no new research action |

### State and Decision Ownership Matrix

| State or decision | Business question | Canonical record and field | Authorized writer | Readers | Derived copies | Allowed transitions | Conflict resolution |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Database schema readiness | Is the database prepared for this application version before runtime work starts? | Dedicated bootstrap status table record: `database_bootstrap_status.status`, with `schema_version`, timestamps, and safe failure reason | Database bootstrap command only | API readiness, worker startup, local test setup, operator health view, UI readiness indicator | Logs and health responses | `not_run -> initializing -> ready` or `failed`; `ready -> incompatible` when app expects newer schema; `failed/incompatible -> initializing -> ready` after successful bootstrap | Bootstrap readiness record wins for accepting work. API/worker refuse runtime work when not ready; business records remain unchanged. |
| Runtime business write eligibility | May API routes or worker activities write business records now? | API/worker readiness gate derived from `database_bootstrap_status.status` plus required dependencies | API lifespan and worker startup checks | Research routes, worker activities, health endpoints | Process-local readiness flag | `blocked -> allowed` after readiness passes; `allowed -> blocked` on startup failure or dependency recheck failure | If readiness and store access disagree, store access failure is surfaced as operational unavailability; no schema repair is attempted in the request path. |
| Research workflow status | What stage or terminal outcome should the operator see for a research task? | `research_runs.status`, `status_version`, failure fields, and transition audit in `ResearchStore` | Unified LangGraph workflow through guarded `ResearchStore` methods | UI, API routes, RuntimeService, graph nodes, worker continuations | LangGraph checkpoints, Temporal history, logs | Existing transition table in `ResearchStore`; unchanged by this feature | Stored research row wins. Database initialization failure does not rewrite research status. |
| Agent action authority | May a proposed agent/platform action execute? | Runtime assignment, step, grant, counters, and authorization decision records in `RuntimeStore` | `RuntimeService` | Unified graph nodes, governed MCP host, admin/audit reads | Safe logs/read models | Existing allow/deny decisions; unchanged by this feature | Missing database readiness denies work before RuntimeService is asked; RuntimeService remains sole authority once runtime is ready. |
| Durable worker polling readiness | May the Temporal worker poll and execute activities? | Worker process readiness derived from database bootstrap readiness and Temporal connectivity | Durable worker startup | Temporal worker runtime, logs, operator process status | Container health/status | `not_started -> ready` or `failed`; no polling before ready | If database readiness fails, worker exits or remains not-ready and does not process activities. Temporal history does not become business state. |
| Store schema setup authority | Who may create/alter/drop/repair platform schema? | Bootstrap execution record/log plus `database_bootstrap_status` readiness marker | Database bootstrap command | API startup, worker startup, tests, operator docs | Store-level schema fragments as implementation inputs | `not_run -> initializing -> ready/failed`; repeat run may remain `ready` if compatible | Runtime store methods cannot override bootstrap state. Any accidental runtime DDL is a test failure. |
| UI platform readiness indicator | Should the operator see the platform as ready for research? | API readiness/service-health response derived from bootstrap readiness and required dependencies | API health/readiness layer | React UI, operator | UI display state | `unknown/loading -> ready` or `not_ready`; `ready -> not_ready` after failed refresh | API readiness wins. UI does not infer readiness from research status or local component state. |

For workflows:

- The UI displays `research_runs.status`; this feature does not change that.
- RuntimeService evaluates stored runtime assignment/authorization facts only
  after API/worker readiness has passed.
- Interrupted research resumes from LangGraph checkpoints only after bootstrap
  readiness passes; checkpoints remain execution bookmarks.
- Retry and concurrent request behavior for research runs remains governed by
  `ResearchStore` status/version and target-key locks.
- If database initialization is unavailable, new runtime work is rejected as
  operationally unavailable. Existing business records are not rewritten.

## Project Structure

### Documentation (this feature)

```text
specs/010-database-bootstrap/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── database-bootstrap-contract.md
└── tasks.md
```

### Source Code (repository root)

```text
apps/api/app/
├── persistence.py                    # Shared persistence/bootstrap helpers
├── main.py                           # API startup/readiness gates
├── durable_execution/
│   └── worker.py                     # Worker startup readiness gate
├── web_research/store.py             # Runtime business store; no lazy DDL after refactor
├── agent_runtime/store.py            # Runtime authority store; no lazy DDL after refactor
├── agentic_research/store.py         # Topic/report store; no lazy DDL after refactor
├── evidence_summaries/store.py       # Summary store; no lazy DDL after refactor
├── web_trust/store.py                # Trust store; no lazy DDL after refactor
├── identity/store.py                 # Identity store; no lazy DDL after refactor
├── identity/audit.py                 # Security audit store; no lazy DDL after refactor
└── local_models/store.py             # Local model config store; no lazy DDL after refactor

apps/api/tests/
├── test_database_bootstrap.py        # New bootstrap/readiness coverage
├── test_web_research.py              # API readiness/research start regression coverage
└── test_durable_execution.py         # Durable worker startup/readiness coverage

compose.yaml                         # Local startup ordering/readiness adjustments
docs/
├── local-evidence-intelligence.md    # Operator startup documentation
└── adr/                              # ADR update only if planning finds a durable boundary change
```

**Structure Decision**: Keep database initialization code inside the API package
because it reuses existing store schema definitions and deployment settings.
Expose it as a bootstrap command that Docker Compose runs through a short-lived
`database-bootstrap` service after Postgres is healthy and before API/worker
readiness. API and worker processes verify the bootstrap record but do not run
DDL. Do not introduce a separate migration service, second database project, or
parallel workflow.

## Phase 0 Research

See [research.md](research.md).

## Phase 1 Design

See [data-model.md](data-model.md), [contracts/database-bootstrap-contract.md](contracts/database-bootstrap-contract.md), and [quickstart.md](quickstart.md).

## Post-Design Constitution Re-Check

- **Canonical owner:** Still passed. Database bootstrap owns only operational
  schema readiness. Existing stores retain business-record ownership.
- **State and decision ownership:** Passed. Matrix identifies bootstrap
  readiness, worker polling readiness, runtime write eligibility, and confirms
  research status/authority remain unchanged.
- **No parallel authority:** Passed. No new research workflow, policy authority,
  store of business truth, Temporal workflow, MCP tool, or model capability is
  introduced.
- **Selected foundations:** Passed. LangGraph, RuntimeService, Temporal, and
  PostgreSQL roles remain aligned with the constitution and ADR 0016.
- **Model boundary:** Passed. No model-facing capability is added.
- **Migration and retirement:** Passed. Lazy runtime schema setup is the
  superseded behavior. It can be removed after bootstrap/readiness tests prove
  stores can operate against an initialized database without running DDL.
- **Operational checkpoint:** Passed. Trigger, owner, canonical operational
  state, direct execution rule, no-human-decision boundary, and exclusions are
  documented.

## Complexity Tracking

No constitution violations are planned. The feature intentionally avoids adding
a full migration framework in this slice because the existing schema fragments
are already colocated with the owning stores and the immediate risk is when DDL
runs, not whether every schema statement has been converted to a numbered
migration. A future migration framework may be evaluated separately if schema
history becomes difficult to maintain.
