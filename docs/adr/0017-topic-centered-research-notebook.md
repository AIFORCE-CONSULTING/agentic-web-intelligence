# ADR 0017: Make Research Topics the Operator-Facing Notebook

- Status: Accepted
- Date: 2026-10-22
- Amends: ADR 0016

## Context

The platform currently treats each operator question as a research run. The
unified LangGraph workflow can discover sources, apply local trust policy,
collect qualified evidence, create summaries, and generate a grounded report.
This is a useful research sequence, but a report attached to one run is not a
useful long-lived place to build understanding across many related questions.

An operator researching a subject such as **Agentic web** needs to return over
time, ask follow-up questions, retain useful sources, and see what changed in
the current understanding. The operator also needs a required evidence-review
decision to remain visible rather than quietly starting more work in the same
subject while it waits.

The existing architecture already has authoritative owners for the underlying
work: `ResearchStore` owns a run's official status, `WebTrustStore` owns exact
evidence review decisions, `AgenticResearchStore` owns planned topics,
relevance, coverage, and report artifacts, RuntimeService authorizes external
work, LangGraph coordinates the application workflow, and Temporal handles
durable work selected by deterministic thresholds.

## Decision

The platform provides a workspace-scoped **Research Topic**: a durable operator
notebook that groups related research questions, retained source provenance,
and immutable wiki revisions.

### A topic is not a second workflow

A Topic surrounds existing research runs. It does not replace or duplicate the
unified LangGraph workflow. `research_runs.status` remains the one official
status for each question and is still written only by the unified graph through
`ResearchStore`.

`ResearchReportingService` becomes the single publisher of an immutable topic
wiki revision. It uses a fixed snapshot of qualified stored summaries already
associated with that topic. It publishes no revision when the snapshot has not
changed. The existing standalone run-report experience is retired as the
primary operator experience after the topic notebook cutover.

### Topic-scoped reuse and provenance

The same normalized question reuses an existing run only within the selected
topic. The same question may be investigated in a different topic. A source is
retained once in a topic library while append-only provenance records preserve
every question that introduced or reused it.

### Required feedback is visible and cannot be bypassed

The topic workspace derives a **Needs your decision** queue. It does not store a
topic-level workflow status. A queue item exists when an associated evidence
version has `web_evidence_trust_evaluations.disposition = review_required` and
does not have an active human decision in
`web_evidence_trust_overrides.outcome` of `accepted` or `rejected`.

Before creating or reusing a question in that topic, `TopicWorkspaceService`
reloads this derived queue from the canonical records. If an item remains, the
request returns the item and creates no new run. The operator uses the existing
accept or reject endpoint for the exact source version. Both outcomes resolve
the feedback loop: acceptance can make evidence eligible under the existing
trust rules, while rejection keeps it excluded. An accepted decision with an
expiry becomes pending again after that expiry; rejection does not expire in the
current workflow.

**Example:** A source in **Agentic web** requires review. The operator sees it
in **Needs your decision** and rejects it. The source remains visible but
excluded. The stored rejection resolves the required review, so the operator
can ask the next question in **Agentic web** without waiting for the rejected
source to become eligible.

### Read-only Studio boundary

The Topic workspace will show a Studio area as the future home for grounded
briefings, slides, mind maps, tables, flashcards, and other outputs. This ADR
does not authorize creating any Studio artifact. Each output requires a later
specification for grounding, cost, persistence, and review.

## Consequences

- Operators gain one durable place to build a source-grounded understanding of
  a subject over multiple questions.
- The existing LangGraph, RuntimeService, trust, review, Temporal, and source
  summary boundaries stay in force.
- PostgreSQL gains topic, topic-to-run, topic-source provenance, wiki revision,
  revision input, contribution, exclusion, and update records.
- The UI no longer treats a single run report as the primary research product.
- Test-era standalone report records may be removed under the approved
  clean-start policy; no backwards-compatibility path is required.

## References

- [ADR 0016: Govern the local agentic research workflow](0016-governed-local-agent-capability-requests.md)
- [Architecture constitution](../architecture-constitution.md)
- Active implementation specification: `specs/011-topic-research-wiki/spec.md`
