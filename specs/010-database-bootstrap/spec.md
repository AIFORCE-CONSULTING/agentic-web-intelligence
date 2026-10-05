# Feature Specification: Database Bootstrap Before Runtime

**Feature Branch**: `010-database-bootstrap`  
**Created**: 2026-10-04  
**Status**: Draft  
**Input**: User description: "Move schema setup out of lazy runtime store initialization and into an explicit database bootstrap step before API and worker accept real work. Database bootstrap/migrations run first, then API starts, then worker starts. Runtime code only does runtime work and must never change schema during a user workflow."

## User Scenarios & Testing *(mandatory)*

<!--
  IMPORTANT: User stories should be PRIORITIZED as user journeys ordered by importance.
  Each user story/journey must be INDEPENDENTLY TESTABLE - meaning if you implement just ONE of them,
  you should still have a viable MVP (Minimum Viable Product) that delivers value.
  
  Assign priorities (P1, P2, P3, etc.) to each story, where P1 is the most critical.
  Think of each story as a standalone slice of functionality that can be:
  - Developed independently
  - Tested independently
  - Deployed independently
  - Demonstrated to users independently
-->

### User Story 1 - Start the Platform Only After the Database Is Ready (Priority: P1)

As an operator starting the local platform, I want Docker startup to prepare the database before the API and worker accept research requests so that active research runs do not collide with table, column, index, or constraint changes.

**Why this priority**: This prevents startup and first-use schema changes from interrupting live research workflows with database locks or deadlocks.

**Independent Test**: Can be tested by starting the platform from an empty database and confirming the Docker-started bootstrap step completes before the API and worker report ready.

**Acceptance Scenarios**:

1. **Given** an empty local database, **When** the Docker stack starts, **Then** a dedicated database bootstrap step completes before research requests can be accepted.
2. **Given** database initialization fails, **When** the Docker stack starts, **Then** the API and worker do not accept research work and the operator receives a clear readiness failure.

---

### User Story 2 - Keep Runtime Work Separate From Schema Changes (Priority: P2)

As a developer or maintainer, I want runtime services to assume the database is already initialized so that normal research work only reads and writes business records.

**Why this priority**: This keeps user workflows predictable and removes a hidden source of database locking during search, extraction, summarization, and reporting.

**Independent Test**: Can be tested by exercising API and worker startup after initialization and confirming runtime request paths do not attempt table, column, index, or constraint setup.

**Acceptance Scenarios**:

1. **Given** an initialized database, **When** a user starts a research run, **Then** the API and worker only create or update runtime records and do not perform schema setup.
2. **Given** an incompatible or missing schema, **When** API or worker startup checks run, **Then** startup fails clearly instead of silently changing the schema during the first user action.

---

### User Story 3 - Make Initialization Status Inspectable (Priority: P3)

As an operator troubleshooting the local platform, I want to know whether database initialization succeeded, failed, or is out of date before I run research, including a clear ready indicator in the UI.

**Why this priority**: Clear initialization status reduces confusion when containers restart, the database is purged, or schema expectations change between versions.

**Independent Test**: Can be tested by checking readiness after successful initialization and after intentionally missing or incompatible initialization, then confirming the UI displays the matching ready/not-ready state.

**Acceptance Scenarios**:

1. **Given** the database is initialized, **When** readiness is checked, **Then** the platform reports database readiness as healthy and the UI shows a green ready indicator.
2. **Given** the database is missing required setup, **When** readiness is checked, **Then** the platform reports a clear database initialization problem and the UI does not show the system as ready.

---

### Edge Cases

- Database initialization is attempted while another initialization is already running.
- API starts before the Docker bootstrap step completed.
- Worker starts before the Docker bootstrap step completed.
- Initialization partially completes and then fails.
- The database is purged in local testing and the platform is started again.
- A new application version expects a schema change that has not been applied yet.
- A long-running research workflow is active while an operator restarts containers.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The local Docker stack MUST run a dedicated database bootstrap step that prepares all required tables, columns, constraints, and indexes before API and worker processes accept research work.
- **FR-002**: API and worker startup MUST verify that the required database initialization has already completed before reporting ready for research work, but API and worker runtime paths MUST NOT run schema setup themselves.
- **FR-003**: Runtime request paths MUST NOT create, alter, drop, or repair database schema while processing user actions or background workflow steps.
- **FR-004**: If database initialization is missing, incomplete, incompatible, or failed, the API and worker MUST fail readiness clearly instead of attempting schema changes during first use.
- **FR-005**: Initialization status MUST be visible enough for an operator to distinguish "database not initialized" from ordinary runtime failures such as model unavailability, extraction failure, or trust-policy blocking.
- **FR-006**: Initialization failure MUST NOT mark research runs, evidence, summaries, keywords, reports, trust decisions, or audit records as failed business outcomes.
- **FR-007**: Re-running initialization against an already initialized database MUST be safe and MUST NOT duplicate business data.
- **FR-008**: Local development and test workflows MUST still support starting from an empty database without requiring manual table creation by the operator.
- **FR-009**: Long-running research workflows MUST never depend on schema setup happening mid-run.
- **FR-010**: The feature MUST preserve existing business records when applying compatible initialization updates.
- **FR-011**: The operator UI MUST show a clear ready/not-ready indicator for the platform readiness state that includes database bootstrap readiness.

### Authority and Safety Boundaries *(include for agent, workflow, or external-action features)*

- **Authorized actors**: The Docker-started database bootstrap command, local development tooling, and test setup may request database initialization. End users, API routes, durable worker activities, and local models may not request schema changes.
- **Human-only decisions**: Operators decide when to intentionally reset or purge local test data. Agents and models must not purge, migrate, or modify schema.
- **Agent limitations**: Local models and agentic workflows never receive schema-management capability and cannot declare the database initialized.
- **Canonical record**: Research runs, evidence, summaries, keywords, reports, trust decisions, audit records, and workflow statuses remain the business records. Database initialization status is operational readiness, not business truth.
- **Operator-visible states**: Ready means database initialization is complete and runtime work may proceed. Not ready means initialization is missing, incomplete, incompatible, or failed and research work should not start.
- **Decision authority**: Platform readiness checks decide whether API and worker may accept work. Research workflows decide research states only after readiness succeeds.
- **Conflict outcome**: If runtime records and initialization state disagree, initialization readiness wins for accepting new work, while existing business records remain unchanged.
- **Excluded behavior**: This feature does not define a new research workflow, report-quality rule, trust-policy decision, data purge workflow, or user-facing research action.

### Key Entities *(include if feature involves data)*

- **Database Initialization State**: Operational record or observable readiness outcome showing whether required setup completed for the current application version.
- **Runtime Service**: Any API route, background worker, workflow node, or durable activity that processes user research work after startup.
- **Business Records**: Research runs, sources, evidence, summaries, keywords, reports, trust evaluations, human review decisions, and audit history.
- **Initialization Failure**: An operational failure that prevents accepting work but does not by itself change research outcomes.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Starting from an empty local database, Docker startup reaches a ready state without any user research action being required.
- **SC-002**: In a research run that includes search, acquisition, summarization, and reporting, zero schema changes occur after the run begins.
- **SC-003**: If required initialization is missing or incompatible, the API and worker report not-ready status before accepting research work.
- **SC-004**: Re-running initialization against an already initialized database completes without duplicating research, evidence, summary, report, or audit records.
- **SC-005**: Manual testing can distinguish database-initialization failures from model, extraction, trust-policy, or report-generation failures using operator-visible messages or health details.
- **SC-006**: The UI displays a green ready indicator when API readiness, database bootstrap readiness, and required runtime readiness checks have passed.

## Assumptions

- The first version may focus on the local Docker development stack and test environment.
- Existing business data should be preserved unless the operator explicitly performs a local test-data purge.
- Database initialization may remain repeatable, but it must run before runtime work rather than inside first-use request paths.
- This feature does not require changing research behavior, model prompts, trust policy, or final report content.
- Database initialization is packaged as a command used by a dedicated Docker startup step. API and worker processes verify readiness but do not run schema setup.
