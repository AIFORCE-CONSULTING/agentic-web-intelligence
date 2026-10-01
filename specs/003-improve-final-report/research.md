# Research: Grounded Final Reports

## Extend the existing report service and LangGraph node

**Decision:** Keep ResearchReportingService.final_report and the LangGraph generate_final_report node as the only report-generation path.

**Rationale:** They already sit inside the unified workflow and its official status transition. A new report workflow or direct route would duplicate the research lifecycle.

**Alternatives rejected:** A separate report workflow, a report API that invokes Ollama directly, or a general agent that selects report inputs.

## Use a schema-backed JSON draft, then render Markdown in platform code

**Decision:** Request a typed Pydantic JSON draft through Ollama's native schema format. The platform validates it and creates final Markdown, citations, source lists, and exclusions.

**Rationale:** The current nonempty-Markdown check cannot prove topic coverage, source contribution, or safe attribution. Server rendering prevents a model from inventing public URLs or directing a user away from stored evidence.

**Alternatives rejected:** A stronger free-form Markdown prompt, model-authored links, and an external citation system.

## Preserve an immutable report package

**Decision:** Store every operator-facing report package with frozen source-summary inputs, topic associations, contribution mapping, exclusions, quality grade, reasons, and prompt/model/contract versions. Retain each attempted model response and deterministic validation result.

**Rationale:** report_sources is a live data query. A later change to a summary or qualification outcome must not silently rewrite the meaning of a stored report.

**Alternatives rejected:** Retaining only an input hash, rebuilding old reports from live source queries, or creating a second reporting database.

## Use one bounded correction

**Decision:** Make at most two total model attempts: an initial draft and one correction with specific validation feedback. If neither passes, show the best structurally safe draft with a FAIL quality grade; if neither is safe, show a platform fallback evidence briefing with a FAIL grade.

**Rationale:** Small local models sometimes miss structured requirements. One correction offers recovery without unbounded delay, resource use, or hidden looping, while the grade tells the operator exactly what completeness checks did not pass.

**Alternatives rejected:** Unlimited retries, accepting readable but incomplete content, or failing without preserving diagnostic detail.

## Keep report work direct

**Decision:** Continue direct report calls inside the existing LangGraph stage.

**Rationale:** Report work is bounded to two local calls and adds no new external action. Existing Temporal durability remains for preflight and summary work. A provider failure becomes an existing retryable research failure.

**Alternatives rejected:** A new Temporal workflow or MCP/browser report tool.

## Amend ADR 0014

**Decision:** Amend ADR 0014 during implementation.

**Rationale:** This is a refinement to the existing governed local-model response boundary, not a new authority boundary.
