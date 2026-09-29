# Architecture Requirements Checklist: Consolidated Research Architecture

**Purpose**: Review whether the Phase 7.5 specification and plan define a
complete, unambiguous, constitution-aligned architecture consolidation before
implementation tasks are generated.  
**Created**: 2026-09-26  
**Feature**: [Consolidated Research Architecture](../spec.md)

**Note**: This checklist evaluates the quality of the written requirements and
design decisions. It does not test the implementation.

## Requirement Completeness

- [x] CHK001 Are requirements defined for every stage from the operator's
  existing start action through final report completion? [Completeness, Spec
  §FR-001–FR-003]
- [x] CHK002 Are canonical owners documented for operator entry, workflow
  coordination, agent authority, web tools, trust, human review, summaries,
  durable execution, and stored state? [Completeness, Plan §Constitution Check]
- [x] CHK003 Are requirements included for both initial research and the two
  permitted missing-topic search rounds? [Completeness, Spec §FR-018]
- [x] CHK004 Are requirements defined for direct work, durable work, human-review
  waits, restart recovery, and final completion? [Completeness, Spec §FR-015–FR-016]
- [x] CHK005 Are the records that remain authoritative versus temporary
  execution context explicitly distinguished? [Completeness, Spec §Authority
  and Safety Boundaries; Plan §Selected foundations]
- [x] CHK006 Are all components planned for reuse, extension, migration, or
  retirement named with an explicit treatment? [Completeness, Plan §Canonical
  owners; Plan §Implementation Sequence]

## Requirement Clarity

- [x] CHK007 Is “one governed research workflow” defined precisely enough to
  exclude the inline route sequence, plain-Python router, older graph, and
  obsolete durable runtime path? [Clarity, Spec §FR-002–FR-003; Plan §Summary]
- [x] CHK008 Is the distinction between workflow coordination and authority
  decisions clear and consistently stated? [Clarity, Spec §FR-004–FR-005; Plan
  §Selected foundations]
- [x] CHK009 Is the operator's **Discover Sources** action clearly defined as
  authorization to start only the fixed read-only plan, rather than a general
  capability grant? [Clarity, Plan §Operational checkpoint]
- [x] CHK010 Are “canonical stored authority,” “bounded request facts,” and
  “safe human-readable explanation” defined sufficiently for objective review?
  [Clarity, Spec §FR-004, §FR-008–FR-010; Contract §Runtime Authorization]
- [x] CHK011 Are direct-versus-durable selection requirements clear about the
  responsible owner, decision inputs, and actors prohibited from selecting the
  mechanism? [Clarity, Spec §FR-015; Plan §Operational checkpoint]
- [x] CHK012 Is the difference between LangGraph checkpoints and official
  business/audit records explicit enough to prevent checkpoint data becoming a
  second source of truth? [Clarity, Plan §Selected foundations; Data Model
  §LangGraph Thread]

## Requirement Consistency

- [x] CHK013 Do the specification, plan, data model, and contracts consistently
  name RuntimeService as the sole agent-authorization owner? [Consistency, Spec
  §FR-004–FR-011; Plan §Canonical owners]
- [x] CHK014 Do all artifacts consistently require agent-visible web actions to
  pass through the existing governed MCP boundary? [Consistency, Plan §Selected
  foundations; Research §Invoke web capabilities]
- [x] CHK015 Are trust eligibility and topic relevance consistently treated as
  separate decisions owned by different established services? [Consistency,
  Spec §FR-012–FR-014; Plan §Canonical owners]
- [x] CHK016 Are human evidence decisions consistently independent of LangGraph,
  Temporal, and model output across all artifacts? [Consistency, Spec §FR-013;
  Contract §Workflow Continuation]
- [x] CHK017 Does the selective clean-start decision align across the
  clarification, requirements, data model, success criteria, and retirement
  plan? [Consistency, Spec §Clarifications, §FR-021; Data Model §Historical data]
- [x] CHK018 Are source, attempt, retry, and gap-search limits described
  consistently wherever authority, persistence, and tests are discussed?
  [Consistency, Spec §FR-007, §FR-018; Contract §Runtime Authorization]

## Authority and Security Coverage

- [x] CHK019 Are default-deny requirements stated for unknown actions, missing
  records, inactive states, wrong workspaces, wrong tasks, invalid stages,
  undiscovered sources, malformed context, and exhausted limits? [Coverage,
  Spec §User Story 2; Contract §Runtime Authorization]
- [x] CHK020 Are the exact facts that must be reloaded from official stores
  distinguished from facts that a caller or model may supply? [Coverage, Spec
  §FR-004–FR-006; Contract §Request]
- [x] CHK021 Are requirements explicit that both allowed and denied decisions
  are recorded before an allowed action can execute? [Clarity, Spec
  §FR-008–FR-009]
- [x] CHK022 Are forbidden data classes for authorization and checkpoint records
  complete, including credentials, secrets, raw webpage content, and
  model-asserted grants? [Coverage, Spec §FR-010; Data Model §LangGraph Thread]
- [x] CHK023 Are human-only decisions and the model's prohibited capabilities
  exhaustively identified for this feature's scope? [Coverage, Spec §Authority
  and Safety Boundaries]
- [x] CHK024 Is policy versioning defined for both current decisions and future
  rule changes without relying on source-control history? [Completeness, Spec
  §FR-011; Data Model §Authorization Decision]

## Scenario and Recovery Coverage

- [x] CHK025 Are requirements defined for a capability request that becomes
  invalid between authorization and execution because task or step state
  changed? [Coverage, Spec §Edge Cases]
- [x] CHK026 Are concurrent start, resume, and completion scenarios addressed
  with an unambiguous idempotency outcome? [Coverage, Spec §Edge Cases,
  §FR-017]
- [x] CHK027 Are durable continuation requirements complete for success,
  duplicate completion, stale checkpoint, mismatched workspace, failed work,
  and process restart? [Coverage, Contract §Workflow Continuation; resolved by
  the canonical status/version continuation contract]
- [x] CHK028 Are human-review continuation requirements defined for acceptance,
  rejection, expiry, wrong evidence version, and repeated decisions? [Coverage,
  Spec §User Story 3, §Edge Cases]
- [x] CHK029 Is the required outcome specified when no eligible and relevant
  evidence exists for a final report? [Coverage, Spec §Edge Cases, §FR-019]
- [x] CHK030 Are malformed planning and relevance outputs assigned explicit
  failure outcomes that cannot be confused with approval or completion?
  [Coverage, resolved by Spec §FR-020 and Task T041]

## Migration and Retirement Quality

- [x] CHK031 Does every retired component have a documented caller-migration
  condition, test-transfer condition, and removal condition? [Completeness,
  Spec §FR-022–FR-023; Plan §Retire overlap]
- [x] CHK032 Is the boundary between retained product data and resettable local
  execution history specific by record group? [Clarity, Spec §FR-021;
  Data Model §Historical data]
- [x] CHK033 Are the requirements clear about which Admin and operator read
  experiences remain available after obsolete local history is removed?
  [Clarity, resolved by Spec §FR-024, Plan §Durable-work operator view, and
  Contract §Existing Durable-Work API]
- [x] CHK034 Is “zero active callers” defined broadly enough to cover routes,
  application startup wiring, services, workers, workflow registration, tests,
  and documentation examples? [Completeness, Spec §SC-008; Plan §Retire overlap]
- [x] CHK035 Are temporary coexistence conditions bounded so migration cannot
  leave two active authority or orchestration paths indefinitely? [Coverage,
  Constitution Principle V; Plan §Migration and retirement]

## Acceptance Criteria Quality

- [x] CHK036 Can each success criterion be evaluated without interpreting
  subjective terms such as “correct,” “safe,” or “useful”? [Measurability, Spec
  §SC-001–SC-013]
- [x] CHK037 Do the success criteria cover authority, trust exclusion, durable
  resume, idempotency, historical-data treatment, caller retirement, and
  documentation alignment? [Completeness, Spec §SC-001–SC-013]
- [x] CHK038 Are the 100% criteria scoped to named matrices and integration
  scenarios so their denominators are unambiguous? [Clarity, Spec §SC-001–SC-005]
- [x] CHK039 Is architecture-documentation agreement defined against the
  exercised end-to-end path rather than against intended design alone?
  [Measurability, Spec §SC-009]

## Dependencies and Assumptions

- [x] CHK040 Are the required behaviors of the existing identity, MCP, trust,
  review, summary, database, local-model, and durable-execution boundaries
  documented as dependencies rather than silently assumed? [Dependency, Plan
  §Canonical owners]
- [x] CHK041 Is the assumption that the existing source-limit choices, polling
  experience, and API shape remain unchanged consistent with all planned
  workflow-state additions? [Assumption, Spec §Assumptions; Contract §Research
  API]
- [x] CHK042 Is the lifecycle and retention expectation for framework
  checkpoints documented, including setup and obsolete-thread cleanup?
  [Dependency, Data Model §LangGraph Thread; resolved by Plan §Checkpoint
  lifecycle and Spec §FR-034]
- [x] CHK043 Are requirements for failure when PostgreSQL, Temporal, MCP search,
  extraction, or the local model is unavailable complete and assigned to the
  correct owner? [Coverage, resolved by Spec §FR-035–FR-041 and Plan
  §Dependency-unavailable behavior]

## Documentation and Traceability

- [x] CHK044 Does every functional requirement map to at least one user story,
  measurable outcome, contract, or design decision? [Traceability, Spec
  §FR-001–FR-042]
- [x] CHK045 Are ADR 0016, the architecture diagram, glossary, runtime
  documentation, and roadmap each assigned a specific post-implementation
  update responsibility? [Completeness, Spec §FR-025; Plan §Verify and document]
- [x] CHK046 Are references to retired components clearly labeled as migration
  context so future readers do not mistake them for approved target
  architecture? [Clarity, Plan §Project Structure]
- [x] CHK047 Is explicit user architecture approval identified as a gate before
  runtime or workflow implementation tasks begin? [Governance, Plan §Approval
  status]

## State and Decision Ownership

- [x] CHK048 Is `research_runs.status` named as the exact official record for
  the operator-facing research stage and outcome? [Ownership, Spec §FR-026;
  Plan §State and Decision Ownership Matrix]
- [x] CHK049 Is the unified workflow the only status-transition initiator, with
  every write guarded through ResearchStore? [Ownership, Spec §FR-027; Plan
  §Research workflow transition table]
- [x] CHK050 Are RuntimeService, LangGraph checkpoints, and Temporal each
  limited to authority, execution bookmarks, and durable-work tracking
  respectively? [Boundary, Spec §FR-026–FR-033; Plan §State and Decision
  Ownership Matrix]
- [x] CHK051 Is every permitted normal, waiting, failure, retry, and terminal
  research-status transition enumerated? [Completeness, Spec §FR-028–FR-030;
  Plan §Research workflow transition table]
- [x] CHK052 Are retries, concurrent starts, stale checkpoints, version
  conflicts, and duplicate or late Temporal completions assigned deterministic
  outcomes? [Recovery, Spec §FR-031–FR-033; Contract §Workflow Continuation]
- [x] CHK053 Do the UI and RuntimeService read the same canonical research
  status without deriving it from checkpoint or durable-execution state?
  [Consistency, Spec §FR-026; Contract §Research API]
- [x] CHK054 Does every agent-triggered MCP execution audit identify and match
  the exact prior authorization decision, workspace, research task, runtime
  assignment, step, request, tool, and bounded resource? [Traceability, Spec
  §FR-042; Contract §Runtime Authorization]

## Notes

- Check items off as the specification and plan are reviewed.
- Record findings beside the relevant item and update the source artifact, not
  only this checklist.
- Items marked `[Gap]` deliberately call attention to requirements that may need
  strengthening before task generation.
- Checked CHK002, CHK005, CHK008, CHK012, CHK013, CHK026, CHK027, and
  CHK048–CHK053 record the completed C1 documentation remediation. Checked
  CHK042 records the completed C2 checkpoint-lifecycle design. These checks do
  not claim that the corresponding runtime implementation tasks are complete.
  Checked CHK043 records the completed C3 dependency-failure design.
  Checked CHK047 records explicit user approval on 2026-09-26.
  Checked CHK033 records the completed G1 durable-work-view coverage design.
  Checked CHK030 records the completed S1 malformed-output checklist review.
  Checked CHK054 records the completed I1 MCP audit-correlation design.
- The full checklist was reviewed against `spec.md`, `plan.md`, `tasks.md`,
  `data-model.md`, `research.md`, and all four contracts on 2026-09-26.
  CHK025, CHK028, CHK029, CHK034, CHK038, and CHK044 required source-document
  clarification before closure: stale authorization is rechecked before tool
  execution; unresolved, repeated, expired, and mismatched human decisions are
  defined; the no-usable-evidence outcome is grounded; the zero-caller audit
  scope and success-criteria denominators are explicit; and every functional
  requirement range has traceability.
