# Feature Specification: Reliable Summary Recovery

**Feature Branch**: `002-summary-recovery`  
**Created**: 2026-09-29  
**Status**: Draft  
**Input**: User description: "Recover safely when the local model returns a malformed summary response, keep keywords grounded in the summary without a model-generated coverage map, record useful diagnostics, and allow successful sources to continue into the final report."

**Approved Repair, 2026-09-30**: Remove the brittle exact keyword-phrase
rejection rule and make the unified research workflow the sole initiator of
summary work. Preflight retains retrieval and trust enforcement, but it no
longer starts summaries.

## Clarifications

### Session 2026-09-29

- Q: Where should the operator see an exhausted source-summary failure and omitted-source disclosure? → A: Defer the precise presentation to planning; retain the requirement that the information is available to the operator and disclosed in the final report.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Recover From One Invalid Model Response (Priority: P1)

As an operator, I want the platform to make one controlled correction attempt when the local model returns a response that violates the summary contract, so that a temporary model mistake does not unnecessarily stop the research task.

**Why this priority**: Small local models occasionally produce inconsistent structured responses. Bounded recovery preserves the low-cost local model strategy without weakening evidence quality or allowing unlimited work.

**Independent Test**: Provide a first response that is not valid JSON or does not meet the required response shape or keyword-list rules, followed by a valid response. The source summary completes after exactly one corrective attempt, and only the valid response is accepted.

**Acceptance Scenarios**:

1. **Given** an eligible source is being summarized, **When** the first model response violates the summary contract and the second response is valid, **Then** the platform stores the valid result and continues the research task.
2. **Given** a model response violates the summary contract, **When** the platform requests correction, **Then** the correction request identifies the failed requirement without exposing unrelated platform instructions or accepting the invalid response.
3. **Given** a model response is invalid, **When** recovery occurs, **Then** the same trust decision, source version, evidence text, and summary contract remain in force.

---

### User Story 2 - Understand Why a Source Failed (Priority: P1)

As an operator, I want an exhausted summary failure recorded against the affected source in clear language, so that I can distinguish a model-formatting problem from extraction, trust, orchestration, or infrastructure failures.

**Why this priority**: A generic failed workflow leaves the operator unable to diagnose or responsibly retry the work.

**Independent Test**: Return invalid responses for every permitted attempt and verify that the affected source records the attempt count, validation category, prompt version, model version, and a safe operator-facing explanation.

**Acceptance Scenarios**:

1. **Given** every permitted response for one source is invalid, **When** the attempt limit is reached, **Then** that source is marked failed with an explanation that identifies the summary-contract problem.
2. **Given** a failed attempt contains model-produced text, **When** diagnostics are recorded, **Then** sensitive platform instructions are not exposed to the operator and the invalid content is not treated as evidence or a summary.
3. **Given** an operator reopens the research task, **When** the source failed during summarization, **Then** the operator can see that source's failure independently of the overall research status.

---

### User Story 3 - Preserve Useful Research When One Source Fails (Priority: P2)

As an operator, I want research to continue using sources that were summarized successfully when another source exhausts its correction attempts, so that one unreliable model response does not discard otherwise usable work.

**Why this priority**: A multi-source research task should preserve valid evidence while remaining transparent about missing material.

**Independent Test**: Process multiple eligible and relevant sources with at least one successful summary and one exhausted summary failure. Verify that coverage and reporting use only successful stored summaries and disclose the omitted source.

**Acceptance Scenarios**:

1. **Given** at least one source has a valid stored summary and another source exhausts its attempts, **When** research continues, **Then** topic coverage and the final report use only valid stored summaries.
2. **Given** a report is produced after one or more source failures, **When** the operator reviews it, **Then** the research result identifies that some sources were omitted and does not imply that failed sources support the report.
3. **Given** no eligible and relevant source obtains a valid summary, **When** all permitted attempts are exhausted, **Then** the research task fails without producing a final report.

---

### User Story 4 - Complete One Coherent Summary Stage (Priority: P1)

As an operator, I want all summary jobs for one research question to be treated
as one stage of that research task, so that one failed internal job does not
incorrectly end the task while other sources are still being summarized.

**Why this priority**: A source limit of 50 may create several small internal
summary jobs. Those jobs are implementation details; the operator needs one
truthful outcome for the research task, not the status of whichever job finished
most recently.

**Independent Test**: Start a research task with more than five relevant
sources. Make one internal summary job fail and another produce an
evidence-sufficient summary. The task continues to coverage and reporting only
after every internal job has reached a terminal outcome.

**Acceptance Scenarios**:

1. **Given** more than five eligible, relevant sources, **When** the summary
   stage begins, **Then** the platform records the complete fixed source set and
   divides it into internal jobs of no more than five sources each.
2. **Given** one internal job fails while another is still processing, **When**
   the failure is recorded, **Then** the research task remains in its summary
   stage until every internal job is terminal.
3. **Given** at least one source has an evidence-sufficient summary after all
   internal jobs finish, **When** the summary stage completes, **Then** the
   platform continues to coverage and reporting and records the omitted sources.
4. **Given** every source in the fixed summary set ends without an
   evidence-sufficient summary, **When** the last internal job finishes, **Then**
   the research task fails without a final report.

### Edge Cases

- The first response is not valid JSON at all.
- The response has the required fields but contains too few, too many, empty, or duplicate keywords.
- A keyword uses different wording from the summary while still describing a
  concept the summary explains.
- One internal summary job fails while another is still running.
- A duplicate delivery reports the same internal summary job complete twice.
- The correction response fixes one validation error but introduces another.
- The model service becomes unavailable between the first attempt and the corrective attempt.
- A retry or process restart encounters a previously recorded failed attempt.
- Multiple sources fail while at least one source succeeds.
- A source has many chunks and only one chunk exhausts its permitted attempts.
- The final consolidation response is invalid even though all chunk summaries are valid.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The platform MUST reject every model response that is not valid
  JSON or does not satisfy the required response shape, summary limits, or
  keyword-list rules.
- **FR-002**: The platform MUST permit no more than two total model attempts for each summary unit: the initial attempt and one corrective attempt.
- **FR-003**: The corrective attempt MUST state which contract requirement failed and MUST request a complete replacement response rather than modifying or accepting the invalid response.
- **FR-004**: The corrective attempt MUST use the same source evidence, trust outcome, requested summary purpose, and output requirements as the initial attempt.
- **FR-005**: The platform MUST validate the corrective response with the same rules used for the initial response.
- **FR-006**: The platform MUST record each failed attempt with the affected research task, source version, processing stage, attempt number, validation category, safe validation explanation, prompt version, model version, and timestamp.
- **FR-007**: Chunk and consolidation responses MUST return only a summary and a list of keywords. Final source-summary responses MUST return those fields plus `evidence_sufficient`. No response may include a separate keyword-to-sentence coverage map.
- **FR-008**: The platform MUST require three to five non-empty, unique chunk
  keywords and three to seven non-empty, unique final-source keywords. The
  prompt MUST instruct the model to choose keywords that the summary explains,
  but a keyword is not rejected solely because its exact wording does not appear
  in the summary.
- **FR-009**: Chunk summaries MUST contain three to five keywords. Completed source summaries MUST contain three to seven keywords.
- **FR-010**: Invalid model output MUST NOT be stored or presented as an accepted source summary, keyword set, topic-coverage contribution, or final-report input.
- **FR-010a**: A final response with `evidence_sufficient: false` is a valid completed source-summary outcome, not a model-contract failure. The platform stores it for operator review but excludes it from topic coverage and final-report input.
- **FR-011**: After all permitted attempts fail, the platform MUST mark the affected source as failed and provide a plain-language operator explanation.
- **FR-012**: A failed source MUST NOT cause already valid summaries for other sources to be deleted, invalidated, or regenerated.
- **FR-013**: When at least one eligible and relevant source has a valid stored summary with `evidence_sufficient: true`, the platform MUST continue coverage assessment and report generation using only those qualified stored summaries.
- **FR-014**: A research result produced with omitted sources MUST identify the number of omitted sources and make their safe failure or insufficiency outcome available to the operator. The precise operator presentation will be selected during planning.
- **FR-015**: When no eligible and relevant source has a valid stored summary with `evidence_sufficient: true`, the platform MUST fail the research task and MUST NOT produce a final report.
- **FR-016**: Repeated delivery, retry, or restart of the same summary work MUST NOT create additional accepted summaries or exceed the two-attempt limit for the same summary unit.
- **FR-017**: Existing trust-policy decisions, human-review decisions, source reuse, and evidence eligibility MUST remain unchanged by summary recovery.
- **FR-018**: The platform MUST distinguish contract validation failures from model-service unavailability, extraction failure, trust exclusion, and workflow infrastructure failure in stored and operator-visible outcomes.
- **FR-019**: Stored diagnostics MUST be sufficient to reproduce which contract and model configuration were evaluated while excluding credentials and hidden platform instructions.
- **FR-020**: The unified research workflow MUST be the only component that
  initiates summary work for a research task. Preflight may retrieve evidence,
  record retrieval facts, and apply trust policy, but MUST NOT start summary
  work.
- **FR-021**: Before the unified workflow starts summaries, it MUST persist one
  fixed summary-work set containing every eligible, relevant source selected for
  that summary stage. Sources are partitioned into internal jobs of no more than
  five sources solely to bound local-model work.
- **FR-022**: The summary-work set MUST remain pending until every member job
  reaches a terminal outcome. A failed member job MUST NOT by itself fail the
  research task.
- **FR-023**: The summary-work set MUST complete when all member jobs are
  terminal and at least one evidence-sufficient source summary exists. It MUST
  fail only when all member jobs are terminal and none produced an
  evidence-sufficient source summary, or when a stored state conflict prevents
  a safe decision.
- **FR-024**: The user interface MUST display the combined summary-work-set
  outcome for the research task, including total successful and failed sources;
  it MUST NOT present only the latest internal job as the task-wide result.

### Authority and Safety Boundaries

- **Authorized actors**: An authenticated operator starts or retries a research task. The platform may perform the single bounded corrective attempt automatically as part of that authorized task.
- **Human-only decisions**: Evidence acceptance, trust overrides, and changes to trust policy remain human decisions and cannot be created by summary recovery.
- **Agent limitations**: The model may propose summary content and keywords only. It cannot relax validation, increase attempt limits, mark its own response valid, change source eligibility, or choose which failed output to retain.
- **Canonical record**: The research record remains the official
  operator-facing workflow status. The summary-work-set record is the official
  answer to whether the collection of internal summary jobs for the current
  research stage is still pending, completed with usable evidence, or failed.
  Accepted source summaries and their keyword lists remain the only summary
  inputs to coverage and reporting. Failed-attempt records explain recovery
  history but never replace accepted evidence or summaries.
- **Operator-visible states**: A source may be awaiting summarization, summarizing, summarized, retrying after an invalid response, or failed after exhausting attempts. A research task may continue with omissions when usable summaries remain, and fails when none remain.
- **Decision authority**: The model supplies candidate content. Platform validation decides whether each response satisfies the contract. Existing trust and review authorities continue to decide whether evidence may enter summarization.
- **Conflict outcome**: If stored attempts, accepted summaries, or workflow state disagree, the platform fails safely, preserves the previously accepted summary if one exists, and presents the conflict for diagnosis rather than accepting a new model response.
- **Attempt reservation and recovery**: Before asking the model for a response, the platform reserves either attempt one or attempt two for the exact summary unit and its current operator-authorized regeneration cycle. A second worker that sees the reservation does not call the model. The reservation expires at the configured model-request timeout plus 30 seconds. When it expires, the platform records a dependency failure and does not silently issue another request. An ordinary worker retry or restart remains in the same cycle; only an explicit operator-authorized regeneration starts a new cycle with a fresh two-attempt allowance.
- **Dependency-failure outcome**: If a model-call reservation expires or the
  provider cannot return a response, the affected source transitions from
  summarizing to failed with the safe category
  `model_dependency_unavailable`. The summary-work set remains pending until
  every member job is terminal; it fails only if no evidence-sufficient source
  summary remains or if a stored state conflict prevents safe continuation.
- **Failure-category vocabulary**: The platform uses these safe, typed outcomes across the existing source and execution records: `summary_contract_exhausted`, `model_dependency_unavailable`, `evidence_trust_blocked`, `evidence_review_required`, `evidence_extraction_unavailable`, `workflow_infrastructure_failed`, and `state_conflict`. Each category has one fixed operator-facing explanation. Categories communicate the stage that stopped work; they do not change trust-policy authority or grant the model any decision-making power.
- **Excluded behavior**: This feature does not change extraction, trust rules, review acceptance, topic relevance, source discovery, model selection, or model-provided access to tools. It does not create an unbounded repair conversation.

### Key Entities

- **Summary unit**: One bounded piece of work requiring a model response, such as a source chunk, an intermediate consolidation group, or a final source summary.
- **Summary attempt**: One model response evaluated for a summary unit, including its attempt number, outcome, model and prompt versions, validation category, and timestamp.
- **Summary-work set**: The persisted collection of all internal summary jobs
  selected by the unified workflow for one research task and one summary stage.
  It records whether all jobs are still pending, completed with usable evidence,
  or failed with no usable evidence.
- **Accepted source summary**: A source-level summary and keyword list that passed all contract validation and may contribute to topic coverage and reporting.
- **Source summary failure**: The operator-visible record that a particular source could not produce a valid summary within the permitted attempts.
- **Research omission**: A reference from a continuing research result to a source excluded because summarization failed, without treating that source as support for the report.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In validation testing, 100% of responses that are malformed or
  violate summary or keyword-list shape rules are rejected and never contribute
  to topic coverage or a final report.
- **SC-002**: In validation testing, 100% of cases with an invalid first response and valid corrective response complete that summary unit in no more than two total attempts.
- **SC-003**: In validation testing, no summary unit exceeds two total model attempts across retries, duplicate delivery, or process restart.
- **SC-004**: Every exhausted source failure displays a plain-language explanation and records the validation category, attempt count, prompt version, and model version.
- **SC-005**: When one source fails and at least one source succeeds, the research task preserves all successful summaries and produces a result based only on those summaries in every test case.
- **SC-006**: When all eligible and relevant sources fail summarization, no final report is produced in every test case.
- **SC-007**: Operators can distinguish a summary-contract failure from extraction, trust, dependency, and workflow failures using the stored outcome without consulting worker logs.
- **SC-008**: In every multi-job test, the research task reaches coverage only
  after all member summary jobs are terminal; one failed job never ends a task
  that still has a completed evidence-sufficient source.

## Assumptions

- Two total attempts per summary unit provide a reasonable balance between recovery and local resource preservation.
- A research task may remain useful when at least one eligible and relevant source is summarized successfully, provided omitted sources are disclosed and never treated as report support.
- Prompt guidance and keyword-list shape checks are sufficient for the current
  business goal: encouraging stored keywords to describe the saved summary
  without making exact phrase matching a source of false failures. The platform
  does not need a separate model-generated coverage map.
- Validation explanations can be safely categorized and presented without retaining or exposing full raw model responses.
- The existing research, evidence, trust, summary, topic-coverage, and reporting records remain the authoritative product records; this feature adds recovery history rather than replacing them.
- Existing stored summaries that already passed validation do not need to be regenerated solely because this feature is introduced.
