# Research: Topic-Scoped Report Sections

## Extend the existing report service instead of creating a second report path

**Decision:** Keep `ResearchReportingService.final_report` and the LangGraph
`generate_final_report` node as the only report-generation path.

**Rationale:** The existing path already participates in the unified research
workflow and official `research_runs.status` transition. Adding another report
route, worker, or graph would create a second orchestration path for the same
operator-facing report.

**Alternatives considered:** A new report endpoint that directly invokes the
model, a separate report workflow, or a UI-triggered report regeneration action.
These were rejected because they duplicate workflow ownership and blur the
canonical completed-report state.

## Generate topic findings one planned topic at a time

**Decision:** Ask the local model to draft findings for one supplied planned
topic at a time, using only that topic's qualified source summaries.

**Rationale:** The previous whole-report draft required the model to copy topic
IDs, source IDs, topic membership, source lists, and narrative findings in one
response. The observed failures were mostly structure and identifier mistakes,
not failures to understand the content. Scoping each call to one topic lets
platform code own section structure and source membership.

**Alternatives considered:** Keep the whole-report draft and strengthen the
prompt; remove citations entirely; or ask for plain Markdown. These were
rejected because prompt-only fixes still leave the model responsible for too
much structure, while removing citations reduces traceability.

## Use simple report-local citation labels

**Decision:** Assign labels such as `S01`, `S02`, and `S03` in the frozen report
input snapshot. The model may cite only labels supplied for the current topic.

**Rationale:** Small local models are more reliable with short labels than with
labels such as `source-01`. The label is not a database handle for the model; it
is a footnote marker whose meaning is stored by the platform.

**Alternatives considered:** Continue using `source-01`; use URLs as citations;
or use model-authored citation text. These were rejected because the model has
already changed `source-01` into unsupported variants, URLs add unnecessary
prompt bulk, and model-authored links would be unsafe navigation targets.

## Normalize only harmless citation-label variants

**Decision:** Allow deterministic normalization for harmless, unambiguous
formatting differences in source labels, such as lower case or spacing, while
rejecting unknown labels and labels outside the current topic.

**Rationale:** The goal is a useful grounded report, not rejecting otherwise
safe findings because of a trivial formatting variant. However, normalization
must not guess when two labels could be confused or when a label is outside the
topic's allowed source set.

**Alternatives considered:** Require exact label copies only, or loosely map any
nearby label to the closest source. Exact-only behavior is brittle for a small
local model; fuzzy mapping is too risky for citations.

## Render sections, source lists, and links in trusted code

**Decision:** Platform code renders the report sections, source lists, citation
links, exclusions, quality grade, and fallback briefing. The model returns only
topic-level finding text and supplied citation labels.

**Rationale:** The platform owns planned topics, source membership, URLs, source
titles, and stored-summary anchors. Letting the model render the full report
creates opportunities for invented links, legacy or unexpected model-authored
topic fields, and missing source lists.

**Alternatives considered:** Let the model render final Markdown and validate it
afterward, or use model-generated links and sanitize them. These were rejected
because trusted rendering is simpler, safer, and easier to test.

## Preserve existing direct execution for reporting

**Decision:** Keep final-report drafting as direct work inside the existing
LangGraph report node. Do not introduce a new Temporal workflow for report
generation in this feature.

**Rationale:** Reporting remains bounded local inference with no new external
action. Existing Temporal usage remains for durable preflight and summary work.
Model timeout or unusable output becomes a stored fallback or failure-grade
report when inputs can be read and stored.

**Alternatives considered:** A new durable report workflow. This was rejected
because it would add operational complexity without changing the canonical
business state or reducing model brittleness.
