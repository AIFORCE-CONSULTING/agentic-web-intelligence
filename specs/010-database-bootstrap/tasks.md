# Tasks: Database Bootstrap Before Runtime

**Input**: Design documents from `specs/010-database-bootstrap/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/database-bootstrap-contract.md, quickstart.md

**Tests**: Required. This feature changes API readiness, durable worker startup, store connection behavior, and database side effects.

**Organization**: Tasks are grouped by user story so each story can be implemented and tested independently.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish the active feature context and verify the architecture boundary before runtime code changes.

- [X] T001 Review `specs/010-database-bootstrap/spec.md`, `specs/010-database-bootstrap/plan.md`, `specs/010-database-bootstrap/research.md`, `specs/010-database-bootstrap/data-model.md`, and `specs/010-database-bootstrap/contracts/database-bootstrap-contract.md` before editing code
- [X] T002 Confirm the design alignment checkpoint in `specs/010-database-bootstrap/plan.md` is approved before changing runtime startup, worker, or store behavior
- [X] T003 [P] Inspect current lazy schema setup call sites in `apps/api/app/web_research/store.py`, `apps/api/app/agent_runtime/store.py`, `apps/api/app/agentic_research/store.py`, `apps/api/app/evidence_summaries/store.py`, `apps/api/app/web_trust/store.py`, `apps/api/app/identity/store.py`, `apps/api/app/identity/audit.py`, and `apps/api/app/local_models/store.py`
- [X] T004 [P] Inspect API and worker startup/readiness paths in `apps/api/app/main.py`, `apps/api/app/durable_execution/worker.py`, and `compose.yaml`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Add the shared bootstrap boundary and test scaffolding used by all user stories.

**Critical**: No user story implementation should begin until this phase is complete.

- [X] T005 Add failing unit tests for repeatable database bootstrap success, failure, and marker recording in `apps/api/tests/test_database_bootstrap.py`
- [X] T006 Add failing unit tests proving bootstrap does not delete or rewrite business records in `apps/api/tests/test_database_bootstrap.py`
- [X] T007 Add failing unit tests for simultaneous bootstrap attempts and incompatible schema-version readiness in `apps/api/tests/test_database_bootstrap.py`
- [X] T008 Create the database bootstrap boundary in `apps/api/app/database_bootstrap.py` that can run all existing store schema fragments before runtime work
- [X] T009 Add a dedicated database bootstrap readiness marker and status contract in `apps/api/app/database_bootstrap.py`
- [X] T010 Add a safe bootstrap readiness checker in `apps/api/app/database_bootstrap.py` that reports missing, failed, incompatible, and ready states without running DDL
- [X] T011 Reuse the existing advisory-lock pattern from `apps/api/app/persistence.py` inside the bootstrap boundary so only one bootstrap attempt runs at a time
- [X] T012 Update tests in `apps/api/tests/test_database_bootstrap.py` until bootstrap success, failure, idempotency, concurrency, incompatible-version, and non-destructive behavior pass
- [X] T013 Document the bootstrap owner and runtime exclusion boundary in `specs/010-database-bootstrap/plan.md` if implementation discoveries require any clarification

**Checkpoint**: Bootstrap boundary exists, is independently tested, and does not yet require API or worker callers.

---

## Phase 3: User Story 1 - Start the Platform Only After the Database Is Ready (Priority: P1)

**Goal**: API and durable worker only accept work after database bootstrap has completed.

**Independent Test**: Start from an empty database, run bootstrap before API/worker readiness, and verify research requests are not accepted until database readiness succeeds.

### Tests for User Story 1

- [X] T014 [P] [US1] Add failing API readiness tests for missing, failed, and successful database bootstrap states in `apps/api/tests/test_web_research.py`
- [X] T015 [P] [US1] Add failing durable worker startup tests proving the worker refuses to poll work when bootstrap readiness is missing or failed in `apps/api/tests/test_durable_execution.py`
- [X] T016 [P] [US1] Add a failing Compose contract check proving a short-lived `database-bootstrap` service runs after Postgres health and before API and durable worker readiness in `apps/api/tests/test_database_bootstrap.py`

### Implementation for User Story 1

- [X] T017 [US1] Wire database bootstrap readiness into API startup and `/health/ready` in `apps/api/app/main.py`
- [X] T018 [US1] Wire database bootstrap readiness into `/health/services` with operator-facing wording in `apps/api/app/main.py`
- [X] T019 [US1] Wire database bootstrap readiness into durable worker startup before `Worker.run()` in `apps/api/app/durable_execution/worker.py`
- [X] T020 [US1] Add a local bootstrap command entry point in `apps/api/app/database_bootstrap.py`
- [X] T021 [US1] Update `compose.yaml` so a short-lived `database-bootstrap` service runs after Postgres health and API/durable-worker startup waits for successful bootstrap completion
- [X] T022 [US1] Update `apps/api/tests/test_web_research.py`, `apps/api/tests/test_durable_execution.py`, and `apps/api/tests/test_database_bootstrap.py` until P1 startup/readiness tests pass

**Checkpoint**: User Story 1 is complete when empty-database startup reaches ready only after bootstrap and missing bootstrap prevents API/worker work.

---

## Phase 4: User Story 2 - Keep Runtime Work Separate From Schema Changes (Priority: P2)

**Goal**: Runtime stores open connections and process business records without creating, altering, dropping, indexing, or repairing schema during requests, graph nodes, health checks, or Temporal activities.

**Independent Test**: With an initialized database, execute representative API and worker paths and prove no runtime path calls schema setup.

### Tests for User Story 2

- [X] T023 [P] [US2] Add failing tests that patch `execute_schema_setup` and prove research runtime paths do not call it in `apps/api/tests/test_database_bootstrap.py`
- [X] T024 [P] [US2] Add failing tests that patch `execute_schema_setup` and prove worker activity dependency construction does not call it in `apps/api/tests/test_database_bootstrap.py`
- [X] T025 [P] [US2] Add failing regression tests proving store health checks do not run DDL in `apps/api/tests/test_database_bootstrap.py`

### Implementation for User Story 2

- [X] T026 [US2] Remove lazy `execute_schema_setup` calls from `apps/api/app/web_research/store.py` while preserving normal connection-pool behavior
- [X] T027 [US2] Remove lazy `execute_schema_setup` calls from `apps/api/app/agent_runtime/store.py` while preserving normal connection-pool behavior
- [X] T028 [US2] Remove lazy `execute_schema_setup` calls from `apps/api/app/agentic_research/store.py` while preserving normal connection-pool behavior
- [X] T029 [US2] Remove lazy `execute_schema_setup` calls from `apps/api/app/evidence_summaries/store.py` while preserving normal connection-pool behavior
- [X] T030 [US2] Remove lazy `execute_schema_setup` calls from `apps/api/app/web_trust/store.py` while preserving normal connection-pool behavior
- [X] T031 [US2] Remove lazy `execute_schema_setup` calls from `apps/api/app/identity/store.py` and `apps/api/app/identity/audit.py` while preserving normal connection-pool behavior
- [X] T032 [US2] Remove lazy `execute_schema_setup` calls from `apps/api/app/local_models/store.py` while preserving normal connection-pool behavior
- [X] T033 [US2] Update existing tests that depended on lazy schema setup to call the bootstrap boundary explicitly in `apps/api/tests/`
- [X] T034 [US2] Run each new User Story 2 no-DDL test before implementation to confirm it fails, then run the full `apps/api/tests/test_database_bootstrap.py` no-DDL group after implementation

**Checkpoint**: User Story 2 is complete when runtime paths operate only against an already initialized database and no representative runtime test can trigger schema setup.

---

## Phase 5: User Story 3 - Make Initialization Status Inspectable (Priority: P3)

**Goal**: Operators can clearly distinguish database initialization problems from model, extraction, trust-policy, report, or ordinary dependency failures.

**Independent Test**: Check readiness after successful and failed bootstrap attempts and confirm messages are specific, safe, and do not mutate research status.

### Tests for User Story 3

- [X] T035 [P] [US3] Add failing service-health tests for database bootstrap status messages in `apps/api/tests/test_web_research.py`
- [X] T036 [P] [US3] Add failing tests proving initialization failure does not mark research runs failed in `apps/api/tests/test_database_bootstrap.py`
- [X] T037 [P] [US3] Add failing tests proving local model, extraction, trust-policy, and report failures remain distinguishable from bootstrap readiness in `apps/api/tests/test_database_bootstrap.py`
- [ ] T038 [P] [US3] Add failing UI tests for a green ready indicator and not-ready database initialization state in `apps/web/src/App.test.tsx`

### Implementation for User Story 3

- [X] T039 [US3] Add safe operator-facing database initialization details to health responses in `apps/api/app/main.py`
- [X] T040 [US3] Add safe worker startup logging for database initialization failures in `apps/api/app/durable_execution/worker.py`
- [X] T041 [US3] Ensure database bootstrap failure is surfaced as operational unavailability, not a research workflow transition, in `apps/api/app/main.py` and `apps/api/app/durable_execution/worker.py`
- [X] T042 [US3] Add the green ready/not-ready platform indicator to `apps/web/src/App.tsx`
- [X] T043 [US3] Update `docs/local-evidence-intelligence.md` with the new startup order, bootstrap meaning, UI readiness indicator, and troubleshooting guidance
- [X] T044 [US3] Update `specs/010-database-bootstrap/quickstart.md` with the final command names and manual validation steps after implementation details are known

**Checkpoint**: User Story 3 is complete when operators can identify database initialization state without confusing it with research, model, trust, extraction, or report outcomes.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Validate the full behavior, update documentation, and remove any leftover runtime-DDL assumptions.

- [X] T045 [P] Run Ruff for API changes with `docker run --rm -v "${PWD}:/workspace" -w /workspace/apps/api python:3.12-slim sh -lc "pip install --require-hashes --only-binary=:all: -r requirements-dev.lock >/dev/null && ruff check ."`
- [X] T046 [P] Run focused database bootstrap tests with `docker run --rm -v "${PWD}:/workspace" -w /workspace/apps/api python:3.12-slim sh -lc "pip install --require-hashes --only-binary=:all: -r requirements-dev.lock >/dev/null && PYTHONPATH=/workspace/apps/api pytest -q tests/test_database_bootstrap.py tests/test_web_research.py tests/test_durable_execution.py"`
- [X] T047 Run web UI validation for the ready indicator with `docker run --rm -v "${PWD}:/workspace" -w /workspace/apps/web node:22-alpine sh -lc "npm ci && npm run build"`
- [X] T048 Run a Docker Compose smoke test proving `database-bootstrap` completes before API and durable-worker readiness in `compose.yaml`
- [X] T049 Run the full API test suite with `docker run --rm -v "${PWD}:/workspace" -w /workspace/apps/api python:3.12-slim sh -lc "pip install --require-hashes --only-binary=:all: -r requirements-dev.lock >/dev/null && PYTHONPATH=/workspace/apps/api pytest -q"`
- [X] T050 Run documentation validation if docs changed with `docker run --rm -v "${PWD}:/workspace" -w /workspace python:3.12-slim sh -lc "pip install --require-hashes --only-binary=:all: -r docs/requirements.lock >/dev/null && mkdocs build --strict"`
- [X] T051 Run `git diff --check` from the repository root
- [X] T052 Review `apps/api/app/persistence.py`, all store `_connection_pool()` methods, `apps/api/app/main.py`, `apps/api/app/durable_execution/worker.py`, and `compose.yaml` to confirm schema setup is only reachable through the bootstrap boundary
- [X] T053 Update `specs/010-database-bootstrap/tasks.md` checkboxes as tasks complete

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 Setup**: No dependencies
- **Phase 2 Foundational**: Depends on Phase 1
- **Phase 3 User Story 1**: Depends on Phase 2
- **Phase 4 User Story 2**: Depends on Phase 2 and should follow User Story 1 for easier readiness validation
- **Phase 5 User Story 3**: Depends on Phase 2 and can proceed after User Story 1 readiness shape exists
- **Phase 6 Polish**: Depends on implemented user stories

### User Story Dependencies

- **User Story 1 (P1)**: MVP. Establishes bootstrap-before-runtime startup behavior.
- **User Story 2 (P2)**: Removes the old runtime DDL path after bootstrap exists.
- **User Story 3 (P3)**: Improves operator visibility once readiness states exist.

### Parallel Opportunities

- T003 and T004 can run in parallel.
- T014, T015, and T016 can run in parallel.
- T023, T024, and T025 can run in parallel.
- T035, T036, T037, and T038 can run in parallel.
- T045, T046, and T047 can run in parallel after implementation; T048 runs after Compose wiring is implemented.

---

## Parallel Example: User Story 1

```text
Task: "Add failing API readiness tests for missing, failed, and successful database bootstrap states in apps/api/tests/test_web_research.py"
Task: "Add failing durable worker startup tests proving the worker refuses to poll work when bootstrap readiness is missing or failed in apps/api/tests/test_durable_execution.py"
Task: "Add a failing Compose contract check proving the database-bootstrap service runs before API and durable worker readiness in apps/api/tests/test_database_bootstrap.py"
```

---

## Implementation Strategy

### MVP First

1. Complete Phase 1 and Phase 2.
2. Complete User Story 1.
3. Stop and validate that empty-database startup reaches readiness only after bootstrap.
4. Confirm failed or missing bootstrap blocks API/worker runtime work without changing research status.

### Incremental Delivery

1. Add bootstrap owner and marker.
2. Gate API and worker startup on bootstrap readiness.
3. Remove lazy schema setup from runtime stores.
4. Add operator-visible readiness detail and the green UI ready indicator.
5. Validate with focused API, web, and full API tests.

### Architecture Guardrails

- Do not introduce a new research workflow, Temporal workflow, MCP tool, model capability, trust-policy authority, or business store.
- Do not let runtime request paths or Temporal activities run schema DDL.
- Do not mark research runs failed because database initialization failed.
- Do not delete business records during bootstrap.
- Keep LangGraph checkpoints as execution bookmarks and Temporal history as durable execution tracking only.
