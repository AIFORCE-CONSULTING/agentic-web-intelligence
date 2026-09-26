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
