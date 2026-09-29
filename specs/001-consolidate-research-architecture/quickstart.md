# Quickstart: Verify the Consolidated Architecture

Obtain the design checkpoint approval in `plan.md` before runtime edits.

1. Start the existing Docker Compose platform and separately configured local
   Ollama provider.
2. Initialize application schemas and the official LangGraph PostgreSQL
   checkpointer. Apply the documented selective clean start for obsolete local
   records; retain evidence-domain fixtures.
3. Run API lint and tests covering RuntimeService default deny, stored decisions
   before MCP, direct graph execution, Temporal wait/resume, exact review
   resume, URL reuse, idempotency, evidence exclusion, two gap rounds, grounded
   reporting, and zero retired callers.
4. In the existing UI, enter a question, choose a source count, and select
   **Discover Sources** once. Confirm one stored task progresses without a
   second approval or agent screen.
5. Confirm large work continues through Temporal and the same graph resumes
   after API restart.
6. Confirm blocked and unaccepted review-required evidence never reaches model
   context; accept one exact version and verify only it re-enters processing.
7. Run the TypeScript/Vite build and strict MkDocs build.
8. Compare the running path to the updated diagram/glossary and confirm no
   active imports of retired classes or workflows.

Expected result: one Discover action starts one governed, resumable workflow;
RuntimeService records authority, MCP executes allowed web tools, trust/review
stay independent, Temporal resumes LangGraph, and PostgreSQL supplies the
operator-visible record.

## Selective local clean start

The project does not preserve obsolete runtime-control records, old graph
execution history, or obsolete Temporal runtime histories. Evidence, trust,
review, summaries, topics, relevance, coverage, and reports remain product data
and must not be removed by this procedure.

1. Stop the API and Temporal worker so no process can write a checkpoint while
   cleanup is running.
2. From `apps/api`, remove legacy standalone RuntimeService records in bounded
   batches. Repeat the command until it prints `0`:

   ```powershell
   python -m app.agent_runtime.research_workflow delete-obsolete-runtime-records --limit 100
   ```

   This deletes only `agent_runtime_runs` rows whose `research_run_id` is null.
   Child steps, events, memories, and handoffs are removed by their existing
   foreign-key cascades. RuntimeService assignments linked to a research record
   are retained. The command also removes the four superseded
   `agentic_research_*` control, request, attempt, and capability-audit tables;
   their authority and limit responsibilities now belong to RuntimeService.
   Evidence-domain tables are not part of this operation.
3. Delete local graph bookmarks in bounded batches. Repeat until the command
   prints `0`:

   ```powershell
   python -m app.agent_runtime.research_workflow delete-obsolete-threads --limit 100
   ```

   The command enumerates checkpoints with the official saver's `alist()` API,
   collects distinct thread identifiers, deletes each through
   `adelete_thread()`, and calls the saver's idempotent `setup()` afterward. It
   never issues application-authored SQL against LangGraph's tables.
4. Delete histories for the retired Temporal workflow through Temporal's own
   administration API. The query is deliberately restricted to the removed
   workflow type:

   ```powershell
   docker compose exec -T temporal sh -lc 'temporal workflow delete --address "$(hostname -i):7233" --query '\''WorkflowType="GovernedRuntimeWorkflow"'\'' --reason "Retired consolidated runtime workflow" --yes'
   ```

   A response reporting no matching executions is a successful no-op. Do not
   delete candidate-preflight or evidence-summary workflow histories, and do
   not translate Temporal history into research status.
5. Start the API and durable worker. Startup initializes
   `unified-research:v1` and retries the
   oldest 100 completed research threads that lack a successful checkpoint
   cleanup record.
6. Check `/health/services`. A remaining terminal-cleanup backlog must appear as
   degraded readiness. Process another bounded batch with:

   ```powershell
   python -m app.agent_runtime.research_workflow retry-terminal-cleanup --limit 100
   ```

The research row remains the official operator-facing status throughout this
process. Checkpoint deletion cannot complete, fail, reopen, or otherwise alter a
research task.
