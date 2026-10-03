# Agent Runtime and Authority

RuntimeService is the platform boundary that decides what the research agent is
allowed to do. LangGraph coordinates the work; it does not grant permission.
The model can propose a bounded action, but it has no direct MCP, network,
database, browser, filesystem, credential, or Temporal access.

## Production path

The authenticated operator enters a question, chooses a source count, and
selects **Discover Sources**. `POST /v1/research/runs` finds or creates the
research record and enters the unified LangGraph workflow. There is no separate
runtime start endpoint or second agent interface.

Before a graph node uses `web.search` or `web.extract`, RuntimeService reloads
the stored research assignment and evaluates:

- workspace, research, assignment, step, role, and capability identity;
- current official `research_runs.status` and workflow stage;
- capability grant and authority-policy version;
- requested query or discovered source scope; and
- source, attempt, retry, reservation, and gap-search limits.

Every result is an `allow` or `deny` record with a stable reason code, safe
explanation, policy version, and bounded request facts. The allowed decision is
stored before execution and correlated with the governed MCP invocation. The
MCP host rejects calls without that matching stored decision.

RuntimeService does not decide whether evidence is trustworthy or relevant.
EvidenceTrustService owns model-context eligibility, the human review service
owns exact-version acceptance, and TopicRelevanceService owns relevance.

## State boundaries

`research_runs.status` is the official status shown to the operator. The
unified graph is its only writer through ResearchStore. RuntimeService reads
that status while deciding authority but does not maintain a competing workflow
status.

RuntimeStore owns assignments, grants, reservations, counters, authorization
decisions, and their audit history. LangGraph checkpoints are execution
bookmarks only. Temporal histories are durable execution tracking only. Neither
may override canonical business records.

Retries and continuation reload stored authority and business state. A stale
checkpoint, terminal research record, exhausted limit, mismatched workspace, or
conflicting record stops safely instead of repeating an external effect.

## Checkpoint cleanup

LangGraph checkpoints are temporary execution bookmarks. After a research run
reaches `completed`, the platform attempts best-effort cleanup through the
official LangGraph checkpointer API. Cleanup deletes only execution bookmarks;
it does not delete research questions, discovered sources, evidence, summaries,
keywords, trust decisions, final reports, or audit history.

If completed-run cleanup is pending or fails, the completed research run stays
completed. The backlog appears as degraded maintenance in health checks and can
be retried with the bounded maintenance command:

```powershell
python -m app.agent_runtime.research_workflow retry-terminal-cleanup --limit 100
```

Completed-run cleanup backlog does not block a different research request.
Only checkpoint infrastructure that is unavailable for active workflow
execution can make the governed research workflow unavailable.

## Agent-visible capabilities

The versioned `agentic-research-capabilities-v1` catalog contains only bounded:

- `web.search`, with a validated query and result count; and
- `web.extract`, for a URL already discovered for the same research task.

Tool descriptions tell the model what it may request; they are not permission.
The code-owned MCP registry remains the execution catalog. Cookie interaction,
website-provided tools, shell, credentials, and database access are excluded.

## Model evaluation

ADR 0016 selects `qwen3:1.7b` for this bounded workflow based on
`agentic-research-workflow-evaluation-v4`. The evaluation covers topic planning,
relevance, hostile webpage instructions, missing-topic queries, report
grounding, malformed responses, duplicate and ineligible evidence, and fixed
limits. All 20 cases passed five attempts under the recorded model, prompt,
contract, fixture, and deterministic settings.

Run the fixture-only suite from `apps/api` with:

```powershell
python -m app.agent_evaluations --suite research --model qwen3:1.7b
```

The suite does not call live search, extraction, MCP, browser, credentials, or
websites. Re-run it before changing the selected model artifact, model-owned
prompt or contract, or agent capability set.

## Retired runtime path

Phase 7.5 removed the old deterministic planner, first-result executor,
reviewer cycle, standalone control and orchestration services,
`GovernedRuntimeWorkflow`, and `/v1/runtime/runs`. The useful authority checks
were consolidated into RuntimeService and the useful workflow stages into the
one LangGraph. The Admin **Durable Work** view now reads current preflight and
summary records and does not control a retired runtime.

See [ADR 0016](adr/0016-governed-local-agent-capability-requests.md), the
[current architecture](current-platform-architecture.md), and the
[architecture glossary](architecture-glossary.md).
