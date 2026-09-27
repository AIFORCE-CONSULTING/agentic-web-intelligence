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
2. From `apps/api`, run the bounded command below repeatedly until it prints
   `0`:

   ```powershell
   python -m app.agent_runtime.research_workflow delete-obsolete-threads --limit 100
   ```

   The command enumerates checkpoints with the official saver's `alist()` API,
   collects distinct thread identifiers, deletes each through
   `adelete_thread()`, and calls the saver's idempotent `setup()` afterward. It
   never issues application-authored SQL against LangGraph's tables.
3. Clear obsolete local Temporal runtime histories only through the documented
   local Temporal administration/reset procedure. Do not translate that history
   into research status.
4. Start the API. Startup initializes `unified-research:v1` and retries the
   oldest 100 completed research threads that lack a successful checkpoint
   cleanup record.
5. Check `/health/services`. A remaining terminal-cleanup backlog must appear as
   degraded readiness. Process another bounded batch with:

   ```powershell
   python -m app.agent_runtime.research_workflow retry-terminal-cleanup --limit 100
   ```

The research row remains the official operator-facing status throughout this
process. Checkpoint deletion cannot complete, fail, reopen, or otherwise alter a
research task.
