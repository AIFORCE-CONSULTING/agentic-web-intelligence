# Contract: Database Bootstrap Before Runtime

## Operator Contract

### Successful Local Startup

When the local platform starts from an empty database:

1. Postgres becomes healthy.
2. A short-lived database bootstrap service runs the bootstrap command.
3. Database bootstrap prepares required schema and records readiness.
4. API readiness reports ready only after bootstrap succeeds.
5. Durable worker begins polling only after bootstrap succeeds.
6. The UI shows a green ready indicator only after readiness succeeds.
7. A research run can start without any first-use schema setup.

### Missing Or Failed Initialization

When database bootstrap is missing, incomplete, incompatible, or failed:

1. API readiness reports a database initialization problem.
2. Research routes do not accept new research work.
3. Durable worker does not process Temporal activities.
4. Existing research records and artifacts remain unchanged.
5. Operator-facing messages distinguish this condition from model, extraction,
   trust-policy, or report-generation failures.

## Runtime Contract

Runtime stores may:

- open connection pools;
- run ordinary selects/inserts/updates/deletes for their owned business data;
- raise unavailable/incompatible errors when the schema is not ready.

Runtime stores must not:

- create tables;
- alter tables;
- drop or add constraints;
- create indexes;
- repair missing schema;
- silently run schema setup during health checks, API requests, graph nodes, or
  Temporal activities.

## Bootstrap Contract

The bootstrap boundary may:

- execute the existing schema fragments in a controlled pre-runtime phase;
- use a database-level lock to ensure only one bootstrap attempt runs at a time;
- record or expose whether initialization is ready, failed, or incompatible;
- be safely rerun against an already initialized database.

The Docker Compose bootstrap service is the standard local trigger for this
boundary. Tests and developer tooling may invoke the same command explicitly.

The bootstrap boundary must not:

- delete research, evidence, summary, report, trust, runtime, identity, or audit
  business records;
- mark research runs failed;
- grant agent capabilities;
- change trust policy decisions;
- alter report quality outcomes.

## Health Contract

Health/readiness output should distinguish:

- process is alive;
- database bootstrap is ready;
- database bootstrap is missing or failed;
- other dependencies are unavailable;
- workflow checkpoint persistence is degraded or unavailable.

`/health/live` may remain a process-liveness check. Readiness/service health
must not imply the database is ready unless bootstrap has succeeded.

## UI Contract

The operator UI should show:

- a green ready indicator when API readiness confirms bootstrap and required
  dependencies are ready;
- a not-ready/degraded indicator when database bootstrap is missing, failed, or
  incompatible;
- a safe detail message that distinguishes database initialization problems from
  model, extraction, trust-policy, and report-generation failures.

## Test Contract

Tests must prove:

- empty database can be bootstrapped before runtime work;
- initialized database can be used by API/worker without schema DDL;
- missing/incompatible schema blocks readiness clearly;
- simultaneous bootstrap attempts serialize and produce one clear readiness result;
- runtime research work does not execute schema setup;
- re-running bootstrap does not duplicate business records;
- initialization failure does not change research workflow status.
