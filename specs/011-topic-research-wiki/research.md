# Research: Topic Research Wiki

## Extend the existing unified graph

**Decision**: A topic surrounds the existing LangGraph research sequence; it is
not another workflow.

**Rationale**: `UnifiedResearchWorkflowEntry` and the node set in
`apps/api/app/agentic_research/workflow_nodes.py` already own planning, search,
acquisition, trust, relevance, summaries, coverage, and reporting. A second
notebook workflow would duplicate state, retries, and authority checks.

**Alternative rejected**: Browser-side orchestration or a separate wiki graph.
Neither can own durable status safely.

## Preserve `research_runs.status` as the one progress record

**Decision**: The topic UI derives active/waiting state from associated runs.

**Rationale**: `research_runs.status` is already versioned, guarded, and shown
to operators. A topic status would become a competing answer when several
questions run or finish at different times.

**Alternative rejected**: `research_topics.status`.

## Make required human feedback visible and enforceable

**Decision**: A topic derives a **Needs your decision** queue from its
associated runs and existing exact-version evidence-review records. It stores no
topic-level review status. Before a new question is created in that topic, the
topic service checks this queue and returns the pending decision instead of
starting more work.

**Rationale**: Evidence review is useful only when the operator encounters it
at a practical decision point. Reusing `WebTrustStore`'s accepted/rejected
decision preserves the existing authority boundary, while a derived queue makes
the feedback visible without creating a competing workflow state.

**Alternative rejected**: Let the operator ask more questions while review is
pending, or add `research_topics.status`. The first makes a required feedback
loop easy to ignore. The second creates a second answer to a run's progress.

## Distinguish user topics from planned topics

**Decision**: A new Research Topic is operator-owned and workspace-scoped.
`agentic_research_topics` remains the existing model-proposed Planned Topic
record for one run.

**Rationale**: The existing table has a mandatory `run_id` and represents no
more than three model search focuses. It cannot represent a long-lived notebook.

**Alternative rejected**: Reusing the existing planned-topic table.

## Evolve the existing reporting service into the wiki-revision builder

**Decision**: `ResearchReportingService` remains the sole semantic synthesis
service. The graph’s existing final-report node calls it to write a topic wiki
revision from the topic-wide qualified-evidence snapshot.

**Rationale**: It already validates bounded model findings, citations, quality,
and source provenance. A separate wiki writer would leave two active report
paths.

**Alternative rejected**: Keep per-run reports and build another wiki service.

## Publish immutable revisions only when inputs changed

**Decision**: The reporting service compares a deterministic snapshot fingerprint
with the current revision under a topic row lock. A new revision is created only
when qualified topic evidence changed.

**Rationale**: History stays meaningful; two clicks that create no new usable
evidence do not create duplicate wikis.

**Alternative rejected**: One mutable wiki row or one revision per run.

## Scope duplicate questions to the topic

**Decision**: The same normalized question reuses an existing run inside the
selected topic, but can be researched separately in another topic.

**Rationale**: Current `research_target_keys` deduplicates per workspace. A
topic notebook needs distinct context without wasting local resources on
accidental repeated questions.

**Alternative rejected**: Workspace-wide dedupe or unrestricted duplicates.

## Retire standalone run reports after cutover

**Decision**: Clean-start migration removes test-era run report artifacts; topic
wiki revisions replace them as the operator-facing synthesis.

**Rationale**: The user approved no historical-data preservation. Keeping two
report types active would create conflicting product truth.

## Keep Studio read-only

**Decision**: Studio is visible but generates no outputs.

**Rationale**: Each future output needs its own grounding, cost, persistence,
and review design. The notebook is the future source, not a license to create
unreviewed artifacts now.

## External boundaries retained

- **LangGraph** remains the sole application workflow coordinator.
- **Temporal** continues durable preflight/summary work selected by deterministic
  thresholds; it does not own topic state.
- **RuntimeService and governed MCP host** remain the sole authority/execution
  boundaries for search and acquisition.
- **Trust and human review** remain the sole model-context eligibility decision.
- **Ollama/local model** drafts bounded, validated content only.
