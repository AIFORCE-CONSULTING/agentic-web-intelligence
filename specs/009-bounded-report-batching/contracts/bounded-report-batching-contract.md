# Contract: Bounded Final Report Batching

## Existing Report Read Endpoint

`GET /v1/research/runs/{run_id}/report` remains the only report read endpoint.
No report-start or report-regeneration endpoint is introduced.

The response continues to return the newest stored report package with:

- rendered Markdown;
- report quality grade;
- report quality reasons;
- report origin;
- supporting source links;
- exclusions for sources not used in report findings.

If bounded grouping causes a partial report-stage degradation, the response
uses the existing quality reason list to explain the affected topic or group.

## Report Generation Flow

The unified research workflow reaches the existing `reporting` stage and calls
`ResearchReportingService.final_report`.

The service must:

1. Load planned topics in stored order.
2. Load qualified report inputs from existing topic coverage, summary, trust,
   review, and relevance records.
3. Assign or reuse simple report-local labels such as `S01`.
4. Group each topic's qualified summaries into bounded ordered groups using
   both the maximum summary count and prompt input character budget.
5. For each bounded group, create a model prompt containing only:
   - the operator question;
   - the current topic identity and plain-language topic;
   - the source summaries and labels assigned to that group.
6. Validate the model response against the labels supplied to that group.
7. Merge accepted findings from successful groups into one topic section.
8. Render the final report from trusted platform data.
9. Store the report package and bounded group attempts through the existing
   report store.

## Model Response Shape

For one bounded group, the model returns JSON matching this conceptual shape:

```json
{
  "findings": [
    {
      "text": "A concise, evidence-grounded finding for the supplied topic group.",
      "source_refs": ["S01", "S03"]
    }
  ]
}
```

The model response must not contain:

- topic IDs;
- URLs;
- Markdown links;
- source titles as citation substitutes;
- report sections;
- source labels not supplied in the bounded group;
- source labels from another topic or group.

The platform may normalize harmless source-label variants such as `s01`, `S 01`,
or `S1` only when the normalized label is in the same bounded group.

## Validation Contract

The platform accepts a bounded group draft only when:

- the response matches the required JSON shape;
- at least one finding is present;
- every finding contains text;
- every finding cites at least one supplied source label;
- every cited label resolves to one supplied source for the current bounded
  group;
- findings do not cite unknown, cross-topic, or cross-group labels.

Empty responses such as `{}` must be recorded as invalid empty findings, not as
a successful group.

If a first bounded group attempt fails, the correction attempt receives the same
fixed group input plus concise validation feedback. If no safe draft is
available after the bounded attempts, the group contributes a report-stage
quality reason and does not remove accepted findings from other groups.

## Attempt Telemetry

Each stored bounded group attempt records:

- planned topic ID;
- group index;
- attempt number;
- raw response;
- validation errors;
- status;
- failure code;
- duration;
- prompt input character count;
- response character count;
- model name;
- prompt version;
- contract version.

Attempts are unique by report, topic, group index, and attempt number.

## Report Rendering

Trusted platform code renders:

- the report title;
- one section per planned topic in planned order;
- all accepted findings for the topic, merged from successful groups;
- citation links to stored source summaries;
- a topic-level source list for all qualified topic inputs;
- report quality grade and quality reasons outside the model-authored text;
- excluded source explanations.

If some bounded groups fail and others pass, the topic section still shows the
accepted findings and deterministic source list. If all groups for a topic
fail, the topic receives stored-evidence fallback content and a report quality
reason.

## Failure Semantics

The research run fails during reporting only if report inputs cannot be read or
the report package cannot be stored. Model timeout, unavailable model, empty
JSON, malformed output, unsupported labels, or unusable findings result in a
stored report package with quality reasons when storage is available.
