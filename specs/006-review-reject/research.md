# Research: Human Evidence Review Rejection

## Decision: Extend the Existing Web-Trust Review Owner

**Decision**: Add rejection to the existing `EvidenceTrustService` and
`WebTrustStore` review path that already records human acceptance for
review-required evidence.

**Rationale**: The current architecture already puts trust-policy evaluation,
human acceptance, and effective eligibility under the web-trust service/store.
Adding a second review workflow would split authority over the same evidence
decision. Extending the existing owner preserves the boundary: trust policy
decides review is required, the human operator decides accept or reject, and
the workflow only resumes after that stored decision exists.

**Alternatives considered**:

- Add a separate evidence-review service: rejected because it would create a
  second owner for the same human decision.
- Let the LangGraph node store rejection directly: rejected because LangGraph
  coordinates execution and must not own human trust decisions.
- Treat rejection as deleting the source: rejected because rejected evidence is
  still useful for audit and explanation.

## Decision: Store an Explicit Human Review Outcome

**Decision**: Extend the existing human review record with an explicit
`outcome` value of `accepted` or `rejected`. Existing rows without an outcome
are interpreted as `accepted`.

**Rationale**: Today the table named `web_evidence_trust_overrides` effectively
means "a human accepted this review-required evidence." Rejection needs to be a
durable business decision with the same actor, reason, evidence version, run,
workspace, and audit linkage. Adding an outcome keeps one canonical human
review record for exact evidence versions while avoiding a parallel table.

**Alternatives considered**:

- Create a new `web_evidence_review_decisions` table: rejected for this slice
  because the existing override table already owns exact-version human review
  decisions and has workflow-resume linkage.
- Store rejection only on `research_sources`: rejected because source rows are
  candidate/run records, not the canonical trust-review decision.

## Decision: Only Accepted Review Decisions Change Effective Eligibility

**Decision**: Accepted review-required evidence becomes effectively eligible
for automated use. Rejected review-required evidence remains excluded and is
visible with reviewer identity, timestamp, and any optional reviewer note.

**Rationale**: Reject means "the operator reviewed this exact evidence version
and does not allow it into automated model context." That should not mutate the
base trust evaluation or delete the evidence. Filtering should continue to use
effective eligibility: only eligible or accepted review-required evidence can
reach relevance, summaries, keywords, topic coverage, and final reports.

**Alternatives considered**:

- Add a new trust disposition named `rejected`: rejected for this slice because
  rejection is a human decision layered on top of a base `review_required`
  disposition, not a deterministic trust-policy outcome.
- Treat rejection as `blocked`: rejected because blocked is a policy decision,
  while rejection is a human review outcome scoped to one captured version.

## Decision: Resume the Same LangGraph Thread After Accept or Reject

**Decision**: The existing `resume_after_review` path will resume the paused
LangGraph thread after a stored accepted or rejected decision. The resume
payload may carry `accepted` or `rejected`, but the stored review decision is
the official business record.

**Rationale**: The current workflow already uses LangGraph checkpoints to pause
and continue research. Rejection should not start a new research run or create
another workflow. After rejection, the graph reloads canonical trust decisions
and continues with the rejected evidence excluded.

**Alternatives considered**:

- Start a new run after rejection: rejected because the research task and
  existing evidence trail should remain one workflow.
- Create a Temporal workflow for review continuation: rejected because the
  human decision is already durable in PostgreSQL and the graph resume is a
  direct continuation of the existing workflow.

## Decision: Fix the Official Status Transition

**Decision**: Add `evaluating_relevance -> awaiting_review` to the official
`RESEARCH_STATUS_TRANSITIONS` table.

**Rationale**: Review-required evidence can be discovered while the relevance
node is preparing model context. The business status must be allowed to move
from relevance evaluation into human review so the operator sees a real waiting
state instead of an internal stage that cannot progress.

**Alternatives considered**:

- Route every review-required source back through `acquiring`: rejected because
  it misrepresents what happened and complicates the workflow history.
- Let the graph pause without updating `research_runs.status`: rejected because
  the UI reads the official research status, not checkpoints.

## Decision: No Model, MCP, Policy Editing, or Bulk Review Change

**Decision**: This feature adds only one operator-facing reject action and the
related workflow continuation behavior. It does not add model-owned review,
MCP review tools, bulk approval/rejection, policy editing, source deletion, or
domain-level blocking.

**Rationale**: Human review is a trust boundary. Expanding the actor set or the
scope of the decision would change platform authority and needs separate
design approval.

**Alternatives considered**:

- Add automatic rejection for obviously unsuitable sources: rejected because
  this feature is about human decisions after policy review is required.
- Add a domain blocklist action: rejected because rejection is intentionally
  scoped to one source URL and content hash.
