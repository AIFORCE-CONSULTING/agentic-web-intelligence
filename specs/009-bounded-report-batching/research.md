# Research: Bounded Final Report Batching

## Extend the existing reporting service

**Decision:** Keep `ResearchReportingService.final_report` and the unified
LangGraph `generate_final_report` node as the only final-report path.

**Rationale:** The existing path already owns report input selection, report
attempts, validation, quality grading, persistence, and the research workflow's
transition out of `reporting`. Adding a second report service or endpoint would
duplicate the operator-facing report workflow.

**Alternatives considered:** A separate report-regeneration endpoint, a new
Temporal report workflow, or a UI-triggered report builder. These were rejected
because they create another orchestration path for the same business outcome.

## Split large topics into bounded report groups

**Decision:** Split a topic's qualified summaries into bounded groups before
calling the local model. Use a conservative first version aligned with observed
success: no more than seven summaries per group and no more than roughly
10,000 prompt input characters per group, unless a single summary exceeds that
character budget by itself and must be isolated.

**Rationale:** Stored evidence showed a successful run with 7-summary topic
inputs around 10k characters and a failed run with one 15-summary input around
22k characters. The blank `{}` response appeared once in a smaller run but
recovered on retry; it repeated when the topic payload was much larger.

**Alternatives considered:** Increase model timeout, rely only on retry, or
raise Ollama context globally. These may help latency or capacity but do not
reduce the model's task complexity. Bounded groups directly reduce cognitive
and schema-following load.

## Validate and merge findings deterministically

**Decision:** Validate each bounded group independently, then merge accepted
findings into one trusted topic section rendered by platform code.

**Rationale:** A single failed group should not erase validated findings from
other groups. The operator benefits from partial findings as long as the report
plainly marks degraded quality. Platform-owned rendering preserves topic order,
source lists, and links.

**Alternatives considered:** Fail the whole topic when any group fails, or ask
the model to merge subreports. Failing the topic wastes good findings; model
merging reintroduces model ownership of structure and citations.

## Store bounded-group attempt identity

**Decision:** Add group identity to report-attempt diagnostics so attempts are
unique by report, topic, group, and attempt number.

**Rationale:** Existing attempts are unique by report, topic, and attempt
number. Once a topic can have multiple groups, attempt number alone is no
longer enough to identify which payload failed or passed. Operators and tests
need group-specific prompt input character count, response character count,
duration, validation errors, and failure code.

**Alternatives considered:** Store group identity only in validation text, or
create a new report group table. Text-only identity is hard to test and query;
a new table is unnecessary for this focused refinement.

## Reject empty output earlier and give clearer retry feedback

**Decision:** Treat `{}` and missing findings as an explicit empty-output
failure and feed that reason into the one bounded correction attempt.

**Rationale:** The latest failure returned syntactically valid but empty JSON.
The platform caught it later, but the model needs clearer feedback and the
attempt record should explain that the issue was no findings, not search,
trust, extraction, relevance, or summary failure.

**Alternatives considered:** Accept empty findings and render only source lists,
or classify empty output as generic malformed output. Accepting empty findings
would hide the failure; a generic label is less useful for operators and future
tuning.

## Treat Ollama runtime tuning as measurement, not the correctness fix

**Decision:** Include an implementation task to measure/report the relevant
Ollama runtime settings, but do not make runtime tuning the primary correctness
mechanism for this feature.

**Rationale:** Stored research suggests `keep_alive`, context size, loaded-model
count, and parallelism can improve latency and stability. However, the core
failure is a single oversized report payload for a small local model. Bounded
report calls should work even before runtime tuning is optimized.

**Alternatives considered:** Raise `num_ctx` or keep the model loaded as the
only fix. This might reduce some failures but would keep a brittle oversized
prompt shape and would be hardware-sensitive.
