# Research: Database Bootstrap Before Runtime

## Decision: Move Schema Setup To A Bootstrap Boundary

**Decision**: Introduce one database bootstrap boundary that runs required
schema setup before API routes and durable worker activities accept work.
Runtime stores may continue to own their schema fragments as implementation
inputs, but they must not execute DDL from first-use request or activity paths.

**Rationale**: The current pattern runs `execute_schema_setup` from each store's
lazy `_connection_pool()` method. That means API requests, health checks,
LangGraph continuations, and Temporal activities can trigger `CREATE`, `ALTER`,
constraint, and index statements after the platform is already handling work.
The observed deadlocks happened while live summary/research writes overlapped
with schema-level locks. Moving DDL to bootstrap removes that class of runtime
collision without changing research behavior.

**Alternatives considered**:

- Keep lazy schema setup and rely on the advisory lock: rejected because the
  lock serializes schema setup with other setup calls but does not prevent DDL
  locks from colliding with ordinary live workflow transactions.
- Add retry around deadlocks only: rejected as insufficient because it treats a
  lifecycle problem as a transient query problem and still allows schema changes
  during user workflows.
- Adopt a full external migration framework immediately: deferred because the
  urgent fix is lifecycle timing. A future migration framework can be evaluated
  after bootstrap/readiness is explicit.

## Decision: API And Worker Fail Readiness If Bootstrap Has Not Succeeded

**Decision**: API and durable worker startup should verify database bootstrap
readiness before accepting research work. Missing, incompatible, or failed
database initialization should surface as operational unavailability, not as a
research failure.

**Rationale**: The database is required infrastructure. If it is not prepared,
the platform cannot safely process research. The operator needs a clear
readiness signal, while existing research runs and artifacts must remain
unchanged.

**Alternatives considered**:

- Let the first request initialize the database: rejected because this is the
  current risky behavior.
- Let the worker initialize schema inside each activity: rejected because a
  Temporal activity may run while other API or worker transactions are active.
- Mark active research runs failed when initialization is missing: rejected
  because initialization is operational readiness, not a business outcome.

## Decision: Preserve Existing Store Ownership For Business Records

**Decision**: Existing stores remain the owners for their business records:
`ResearchStore`, `RuntimeStore`, `WebTrustStore`, `EvidenceSummaryStore`,
`AgenticResearchStore`, identity/audit stores, and local-model configuration.
The bootstrap boundary owns only schema setup timing/readiness.

**Rationale**: The constitution requires one owner for each responsibility. This
feature should not use a schema change to introduce a second source of truth
for research status, trust eligibility, summary records, or report quality.

**Alternatives considered**:

- Create a new database service that also owns business state: rejected because
  it would duplicate the existing store responsibilities.
- Fold all store logic into one persistence layer: rejected as too large and
  unrelated to the runtime DDL issue.

## Decision: Use A Repeatable Local Bootstrap For Empty Databases

**Decision**: The local development/test flow should still support an empty
database. Bootstrap must be repeatable and safe against an already initialized
database, but it must run before runtime work.

**Rationale**: The platform is still local-first and under active development.
We should keep the easy developer experience while moving the timing to a safe
place.

**Alternatives considered**:

- Require operators to create tables manually: rejected because it is brittle
  and easy to get wrong.
- Purge data on every startup: rejected because this would destroy business
  records and is not needed for schema readiness.

## Decision: Treat LangGraph Checkpoint Setup Separately From Business Schema

**Decision**: LangGraph checkpoint initialization remains a framework
checkpoint concern, but it must still complete before workflow execution.
Business schema bootstrap and checkpoint readiness should both be prerequisites
for accepting research work.

**Rationale**: ADR 0016 and the constitution define LangGraph checkpoints as
execution bookmarks, not business records. This feature should not mix
checkpoint tables with business state, but startup readiness must still ensure
both required persistence layers are available before a graph runs.

**Alternatives considered**:

- Make checkpoint tables business state: rejected by the constitution and ADR
  0016.
- Ignore checkpoint readiness until first workflow execution: rejected because
  this repeats the first-use initialization problem.
