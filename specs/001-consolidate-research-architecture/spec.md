# Feature Specification: Consolidated Research Architecture

**Feature Branch**: `001-consolidate-research-architecture`  
**Created**: 2026-09-26  
**Status**: Draft  
**Input**: User description: "Review roadmap Phase 7.5 Refactoring and specify how to remove the architecture bloat introduced with the agentic research workflow, using the current-state and target-state architecture diagrams and architecture glossary."

## Clarifications

### Session 2026-09-26

- Q: Must historical data be retained through the refactor? → A: No. The
  refactor may start with a clean data set when that is simpler or safer;
  representative historical data may be retained as test fixtures when useful.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Start One Governed Research Workflow (Priority: P1)

As an operator, I enter a research question, choose how many sources to seek,
and select **Discover Sources** once. The platform carries out the approved
research workflow without asking me to choose between old and new execution
paths or exposing a second agent interface.

**Why this priority**: The operator's existing action is the product entry
point. Architecture consolidation has failed if that action still starts a
separate or incomplete workflow.

**Independent Test**: Start research from the existing interface and verify
that one research record progresses through planning, discovery, evidence
review, relevance, summaries, topic coverage, and reporting without creating a
parallel research run.

**Acceptance Scenarios**:

1. **Given** an authenticated operator and a new research question, **When** the
   operator chooses a source limit and selects **Discover Sources**, **Then** one
   governed research workflow starts and its stored progress is returned through
   the existing interface.
2. **Given** a research question that already has stored sources, **When** the
   operator starts research again, **Then** known URLs are skipped or reused
   according to the existing reuse rules and no duplicate evidence records are
   created.
3. **Given** research that requires longer-running processing, **When** the
   platform moves that work to durable execution, **Then** the interface
   continues to show stored progress and the same research workflow resumes at
   the correct stage after the durable work completes.

---

### User Story 2 - Keep Agent Authority Explicit and Explainable (Priority: P1)

As an operator or auditor, I need every agent-requested action to be checked
against the platform's stored assignment, current research stage, resource
scope, and limits so that the model cannot grant itself permission or expand
what it is allowed to do.

**Why this priority**: Consolidating workflow code must not weaken the boundary
between what an agent may propose and what the platform permits.

**Independent Test**: Submit allowed and disallowed capability requests across
different workspaces, research tasks, workflow stages, resources, and limits;
verify that every decision is recorded before an allowed action occurs and that
anything without an explicit permission is denied.

**Acceptance Scenarios**:

1. **Given** an active research assignment with an explicitly granted action,
   **When** the agent proposes that action for an in-scope resource at the
   correct stage, **Then** the platform records an allowed decision before
   performing the action.
2. **Given** an inactive assignment, wrong workspace, wrong research task,
   undiscovered source, exhausted limit, malformed request, or unknown action,
   **When** the agent proposes the action, **Then** the platform denies it and
   records a stable reason and safe explanation.
3. **Given** an action requiring a human decision, **When** the agent requests
   that action without a valid recorded decision, **Then** the request is denied
   and the agent cannot create or imitate the human approval.

---

### User Story 3 - Preserve Evidence Trust and Human Review (Priority: P1)

As an operator, I need the architecture refactor to preserve the existing trust
policy and evidence-review behavior so that only eligible, relevant evidence
enters automated model context.

**Why this priority**: The refactor is intended to remove duplication, not to
replace or bypass the controls already established for web evidence.

**Independent Test**: Process eligible, blocked, and review-required evidence
through the consolidated workflow and verify that only eligible evidence and
explicitly accepted evidence can be summarized or used in a report.

**Acceptance Scenarios**:

1. **Given** captured evidence that is blocked, **When** research continues,
   **Then** the evidence remains stored for explanation but stays outside all
   automated model context.
2. **Given** captured evidence that requires review, **When** no valid human
   acceptance exists, **Then** automated processing pauses or continues without
   that evidence and the agent cannot approve it.
3. **Given** a valid human acceptance for an exact evidence version, **When**
   research resumes, **Then** that decision is enforced independently of the
   workflow or durable-execution mechanism.

---

### User Story 4 - Retire Duplicate Paths Cleanly (Priority: P2)

As an operator or maintainer, I need overlapping workflow and authority paths
removed without leaving hidden callers, duplicate processing, or ambiguous
ownership. Existing local historical data may be reset when preserving it would
make the refactor harder or less reliable.

**Why this priority**: Removing architecture bloat requires a complete move to
the consolidated path, not indefinite compatibility with unused local data or
obsolete execution paths.

**Independent Test**: Run new research through the consolidated path and verify
that no active caller or worker starts a retired path. When representative
historical fixtures are retained, use them to test compatibility; otherwise
verify the documented clean-start procedure.

**Acceptance Scenarios**:

1. **Given** local historical data that is not required for ongoing operation,
   **When** preserving it would complicate or weaken the refactor, **Then** the
   data may be removed through a deliberate, documented clean-start procedure.
2. **Given** representative historical records that are useful for testing,
   **When** they can be retained without constraining the design, **Then** they
   may be preserved as compatibility fixtures.
3. **Given** all active callers have moved to the consolidated workflow,
   **When** obsolete paths are retired, **Then** no route, worker, or service can
   start them.
4. **Given** a retry or restart, **When** an operation resumes, **Then** existing
   records are reused and no duplicate research, evidence, decision, summary, or
   report records are produced.

---

### User Story 5 - Understand the Running Architecture (Priority: P3)

As a product owner or maintainer, I need the roadmap, diagrams, glossary,
decision records, and operating documentation to describe the architecture that
actually runs so future changes do not recreate competing owners.

**Why this priority**: Shared architecture records are the guardrail against
reintroducing the same duplication later.

**Independent Test**: Compare the finished system to each architecture record
and verify that every responsibility has one named owner, every active caller is
shown, and every retired path is identified.

**Acceptance Scenarios**:

1. **Given** the completed refactor, **When** a reviewer follows the architecture
   records from the operator action to stored results, **Then** the documented
   path matches the path exercised by integration tests.
2. **Given** a responsibility such as workflow coordination, agent authority,
   evidence trust, human review, durable execution, or stored state, **When** a
   reviewer consults the architecture records, **Then** exactly one canonical
   owner is identified.

### Edge Cases

- A request is valid when submitted but its assignment or workflow stage changes
  before the requested action executes.
- A discovered URL belongs to another workspace or research task.
- The source limit, retry limit, or missing-topic search limit is reached while
  other work is still completing.
- Durable work completes after an API process restart or after the operator has
  left the page.
- A human acceptance expires or does not match the exact evidence version being
  considered.
- A model returns malformed relevance or planning output.
- A report is requested when no eligible and relevant evidence is available.
- Historical records refer to a workflow or policy version that is no longer
  active.
- Two requests attempt to start or resume the same research work concurrently.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The existing **Discover Sources** action MUST remain the sole
  operator action for starting the complete research workflow.
- **FR-002**: One operator request MUST create or reuse one canonical research
  record and MUST NOT create competing research or runtime records for the same
  work.
- **FR-003**: The platform MUST maintain one coordinated research sequence that
  covers topic planning, source discovery, evidence acquisition, trust
  evaluation, relevance, summaries, coverage checks, bounded missing-topic
  searches, and final reporting.
- **FR-004**: Every agent-proposed external or consequential action MUST be
  authorized from canonical stored identity, assignment, role, current stage,
  resource scope, and applicable limits before execution.
- **FR-005**: An agent-provided role, capability list, workflow state, evidence
  status, or completion claim MUST NOT be accepted as authority.
- **FR-006**: Authorization MUST verify that the requested resource belongs to
  the same workspace and research task, and that a requested source was
  discovered for that task.
- **FR-007**: Authorization MUST enforce source, attempt, retry, and
  missing-topic search limits using stored counts that survive restarts.
- **FR-008**: Every authorization decision MUST contain an allow-or-deny result,
  a stable reason, a safe human-readable explanation, the applicable authority
  policy version, and bounded request facts.
- **FR-009**: Allowed and denied authorization decisions MUST be durably recorded
  before an allowed action is sent for execution.
- **FR-010**: Authorization records MUST exclude credentials, secrets, and raw
  webpage content.
- **FR-011**: Changes to roles, grants, human gates, or authorization conditions
  MUST receive a new policy version so historical decisions remain explainable.
- **FR-012**: Evidence trust eligibility MUST continue to be decided by the
  existing trust-policy owner and MUST NOT be reimplemented by the workflow or
  authority layer.
- **FR-013**: Human evidence acceptance MUST continue to be recorded with the
  human identity, reason, exact evidence-version scope, and optional expiry, and
  MUST be enforced independently of workflow execution.
- **FR-014**: Blocked and unaccepted review-required evidence MUST remain outside
  planning, relevance, summarization, keyword, coverage, and reporting model
  context.
- **FR-015**: The platform MUST choose direct or durable execution according to
  existing deterministic workload rules; neither the model nor the operator may
  choose the execution mechanism.
- **FR-016**: Completion of durable evidence acquisition or summarization MUST
  resume the same research workflow at the correct stored stage.
- **FR-017**: Existing source reuse, URL de-duplication, write idempotency, retry
  limits, and audit behavior MUST be preserved in the consolidated workflow.
- **FR-018**: The missing-topic search process MUST stop after no more than two
  additional rounds.
- **FR-019**: Final reports MUST use only stored evidence that is both eligible
  for automated use and relevant to an approved research topic.
- **FR-020**: Malformed model outputs MUST fail safely and MUST NOT be silently
  interpreted as approval, relevance, or successful completion.
- **FR-021**: The implementation plan MUST explicitly choose, by record type,
  whether existing local historical data will be retained for compatibility
  testing or removed through a documented clean-start procedure. Historical
  retention is not required for feature completion.
- **FR-022**: An overlapping workflow or authority path MUST be retired only
  after all active callers, required records, tests, and operational visibility
  have moved or been preserved.
- **FR-023**: After retirement, no active route, service, worker, or user action
  may start an obsolete workflow or use a competing authority path.
- **FR-024**: The existing durable-work view MUST continue to show records
  created by the consolidated architecture. Displaying records from retired
  local workflows is optional when those records are deliberately removed as
  part of a clean start.
- **FR-025**: Architecture diagrams, the glossary, decision records, runtime
  documentation, and the roadmap MUST be updated to identify the one active
  workflow, authority, trust, human-review, durable-execution, and canonical
  state boundaries.

### Authority and Safety Boundaries

- **Authorized actors**: An authenticated operator may start research and make
  explicitly assigned human decisions. A research agent may propose only the
  bounded research actions granted to its stored assignment. Platform services
  may perform actions only after the applicable authorization and policy checks.
- **Human-only decisions**: Evidence acceptance, overrides, and any future
  approval designated for human judgment remain human-only. An agent cannot
  create, alter, extend, or imitate them.
- **Agent limitations**: The model cannot grant capabilities, select its role,
  modify limits or policy, approve evidence, write arbitrary records, access
  credentials, choose execution infrastructure, or directly control the
  network, database, browser, or operating system.
- **Canonical record**: Research state, assignments, capability decisions,
  trust evaluations, human decisions, evidence, summaries, topic coverage,
  reports, and audit history must survive process restarts in the platform's
  official stored record.
- **Excluded behavior**: This feature does not add new research controls, new
  agent capabilities, editable trust rules, generalized browser control,
  cookie-preference handling, or a replacement authorization product.

### Key Entities

- **Research Task**: The operator's question, requested source limit, current
  progress, and final outcome.
- **Agent Assignment**: The stored identity, role, granted capabilities, active
  state, and relationship to one research task.
- **Capability Request**: A bounded proposal to perform one action for a named
  resource within a research task and workflow stage.
- **Authorization Decision**: The recorded allow-or-deny result, reason,
  explanation, policy version, and bounded facts used for the decision.
- **Evidence Version**: A captured, immutable version of source content with its
  retrieval and provenance facts.
- **Trust Evaluation**: The policy decision controlling whether an evidence
  version may enter automated processing.
- **Human Evidence Decision**: A person's scoped acceptance or override for one
  evidence version, including identity, reason, and optional expiry.
- **Durable Work Item**: A long-running operation tied to the research task and
  the stage that must resume after completion.
- **Workflow Progress**: Temporary coordination context whose important
  business outcomes are reflected in canonical stored records.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In 100% of integration scenarios, selecting **Discover Sources**
  starts or resumes exactly one governed research workflow and creates no
  competing run for the same request.
- **SC-002**: In the authorization test matrix, 100% of explicitly permitted
  combinations are allowed and 100% of unspecified, malformed, out-of-scope,
  inactive, or limit-exhausted combinations are denied.
- **SC-003**: In 100% of tested allowed actions, the authorization decision is
  stored before execution begins; no allowed action lacks a decision record.
- **SC-004**: In 100% of trust and review scenarios, blocked and unaccepted
  review-required evidence is absent from automated model context and final
  reports.
- **SC-005**: All tested long-running acquisition and summary jobs resume the
  same research workflow at the correct stage after completion or process
  restart.
- **SC-006**: Repeated starts, retries, and resumptions produce zero duplicate
  research, source, evidence, authorization, summary, coverage, or report
  records in the integration test suite.
- **SC-007**: All new work is produced through the consolidated path. For each
  historical record type, testing confirms either that selected fixtures remain
  readable or that the approved clean-start procedure removes them without
  leaving active callers or partial state.
- **SC-008**: A repository-wide caller audit finds zero active callers of the
  retired workflow and overlapping authority paths.
- **SC-009**: The final architecture diagram, glossary, decision records,
  runtime documentation, and roadmap identify one owner for every governed
  responsibility and match the paths exercised by end-to-end tests.

## Assumptions

- The existing operator interface, authentication, trust policy, evidence
  review experience, source reuse behavior, summary behavior, source-limit
  choices, and durable-work visibility for newly consolidated work remain
  product requirements.
- The architecture constitution's named owners remain authoritative; changing
  one of those owners is outside this specification and requires a separately
  approved architecture decision.
- Existing model selection and validated prompt contracts remain unchanged by
  this refactor.
- Historical local data is not a product requirement. The implementation plan
  may retain representative records when they improve compatibility testing or
  may deliberately reset them when a clean start makes consolidation simpler
  and safer.
- The current-state architecture diagram and glossary describe the starting
  point. The approved Phase 7.5 roadmap and target-state diagram describe the
  intended consolidation outcome.
