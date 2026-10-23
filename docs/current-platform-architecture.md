# Current Platform Architecture

This is the production architecture after Phase 7.5 consolidation. It uses
large-print text diagrams so it remains readable in the documentation viewer.
See the [architecture glossary](architecture-glossary.md) for each component's
purpose, inputs, outputs, and connections.

## Operator path

```text
[Operator]
    |
    v
[Research UI: question + source count + Discover Sources]
    |
    v
[POST /v1/research/runs]
Authenticate, validate, find or create the research record
    |
    v
[UnifiedResearchWorkflowEntry]
    |
    v
[ONE LANGGRAPH WORKFLOW]
Topics -> Search -> Acquire and trust -> Relevance -> Summaries
       -> Coverage -> Missing-topic search (maximum two rounds)
       -> Grounded report -> Complete
```

The API route is a thin trigger. The graph owns the sequence, but it does not
grant itself authority or replace the services that own business decisions.

## Governed capability path

```text
[LangGraph node proposes a bounded action]
    |
    v
[RuntimeService]
Reload stored assignment, role, grant, stage, resource, workspace and limits
    |
    +-- deny --> [RuntimeStore: decision + reason + policy version]
    |
    +-- allow -> [RuntimeStore: decision + correlation identity]
                     |
                     v
                 [Governed MCP Host]
                 Verify stored allow, then execute only a registered tool
                     |
                     +--> [SearXNG]
                     +--> [Governed web extractor]
```

RuntimeService is the authorization boundary. The MCP host is the execution
boundary. A model can propose an action but cannot call a provider, manufacture
an allow decision, change a limit, or write platform state.

## Evidence and model path

```text
[Captured source]
    |
    v
[CandidatePreflightService] -> [EvidenceTrustService] -> [WebTrustStore]
                                      |
                     eligible only --+
                                      v
                           [TopicRelevanceService]
                                      |
                         relevant only+
                                      v
                           [EvidenceSummaryService]
                                      |
                                      v
                          [EvidenceSummaryStore]
                                      |
                                      v
                         [ResearchReportingService]
```

The local model supports bounded planning, relevance, summarization, keyword,
missing-topic, and reporting decisions. Its output remains untrusted until the
owning service validates it. Blocked or review-required evidence never enters
automated model context unless an authorized human acceptance exists for that
exact review-required evidence version. An authorized human rejection keeps the
exact evidence version excluded and lets the workflow continue without it.

## Durable continuation path

```text
[LangGraph preflight or summary node]
    |
    +-- below threshold --> execute directly --> persist result --> next node
    |
    +-- durable threshold reached
            |
            v
        [Temporal workflow]
        CandidatePreflightWorkflow or EvidenceSummaryWorkflow
            |
            v
        [Owning service/store persists business result]
            |
            v
        [continue_unified_research activity]
            |
            v
        [Resume the same LangGraph thread at its next valid stage]
```

Temporal makes qualifying work restart-safe. It does not decide permission,
trust, research status, or the next business transition. If scheduling or
continuation fails, the owning research record shows the typed failure; a
second workflow path is not started.

## State ownership

| Record | Authorized writer | Readers | Meaning |
| --- | --- | --- | --- |
| `research_runs.status` | Unified graph through `ResearchStore` | UI, RuntimeService, APIs | Official operator-facing workflow status |
| Runtime assignments and decisions | RuntimeService through `RuntimeStore` | Graph, MCP host, Admin view | Who may do what, why, and under which policy version |
| Topics, relevance, coverage, reports | Unified graph through `AgenticResearchStore` | Graph, APIs, UI | Validated research artifacts |
| Trust evaluations and human review decisions | Trust and review services through `WebTrustStore` | Graph, summary service, UI | Whether evidence may enter model context |
| Summary executions and artifacts | EvidenceSummaryService through `EvidenceSummaryStore` | Graph, APIs, UI | Summary work and validated outputs |
| LangGraph checkpoint | LangGraph checkpointer only | LangGraph | Temporary execution bookmark, never business truth |
| Temporal history | Temporal only | Worker and operational tools | Durable execution tracking, never business truth |

Stale checkpoints and Temporal histories never override PostgreSQL business
records. Continuation reloads canonical records and stops on a terminal,
conflicting, or unauthorized state.

## Checkpoint Maintenance

When the unified graph returns and the stored research run is confirmed as
`completed`, `ResearchCheckpointLifecycle` asks the LangGraph checkpointer to
delete that run's execution bookmark thread. The cleanup result is recorded in
`research_checkpoint_cleanups`.

This cleanup is maintenance, not business state. A failed or pending cleanup
does not change `research_runs.status`, does not remove evidence or reports,
and does not block unrelated new research. Health can report pending cleanup as
degraded maintenance so the operator knows there is housekeeping to retry, but
the UI continues to show the official research status from `research_runs`.

## Retired paths

Phase 7.5 removed the duplicate plain-Python agentic router, the earlier
first-result LangGraph executor and reviewer cycle,
`AgenticResearchControlService`, `ResearchOrchestrationService`,
`TemporalRuntimeBoundary`, `GovernedRuntimeWorkflow`, and `/v1/runtime/runs`.
Obsolete test-era rows, checkpoints, and workflow histories were removed under
the approved clean-start policy. None is a fallback or alternate production
path.

## Topic Research Wiki

The current product boundary is documented in ADR 0017. A **Research Topic** is
a durable operator
notebook that groups existing research runs, source provenance, and immutable
wiki revisions. It will extend the current unified graph and stores rather than
create a second workflow or status system.

When evidence in a topic needs human review, the topic workspace
derive a **Needs your decision** queue from the existing trust evaluation and
override records. The queue is an operator view, not stored topic status. It
will require the operator to use the existing accept or reject action before
starting another question in the same topic.
