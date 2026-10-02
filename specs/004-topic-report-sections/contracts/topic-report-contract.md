# Contract: Topic-Scoped Final Report

## Existing Report Read API

`GET /v1/research/runs/{run_id}/report` remains the only report read endpoint.
It requires the existing research read permission and never starts model work.

The response continues to return a stored report package with:

- rendered Markdown;
- model name when available;
- prompt and contract versions;
- `PASS` or `FAIL` quality grade;
- quality reasons;
- report origin;
- supporting-source map;
- exclusions;
- currentness flag.

No new report-start API is introduced.

## Report Generation Contract

The unified research workflow reaches the existing `reporting` stage and calls
`ResearchReportingService.final_report`.

The service must:

1. Load planned topics in stored order.
2. Load qualified report inputs from existing topic coverage, summary, trust,
   and review records.
3. Assign simple report-local labels such as `S01`.
4. For each planned topic, create a topic-scoped model prompt containing only:
   - the operator question;
   - the current topic identity and plain-language topic;
   - the source summaries and labels assigned to that topic;
   - the response schema.
5. Validate the model response against the allowed labels for that topic.
6. Render the final report from trusted platform data.
7. Store the report package and topic-scoped attempts through the existing
   report store.

## Model Response Contract

For one topic, the model returns JSON matching this conceptual shape:

```json
{
  "findings": [
    {
      "text": "A concise, evidence-grounded finding for the supplied topic.",
      "source_refs": ["S01", "S03"]
    }
  ]
}
```

The model must not return:

- topic IDs;
- URLs;
- Markdown links;
- source titles as citations;
- source labels not supplied in the topic prompt;
- source labels from another topic;
- eligibility, trust, review, or workflow decisions.

## Deterministic Validation

The platform validates:

- the response matches the schema;
- every cited label resolves to one supplied source for the current topic;
- harmless label formatting is normalized only when unambiguous;
- findings are not accepted when citations are unknown or cross-topic;
- the topic section itself is always rendered by trusted code.

If a first topic attempt fails, the correction attempt receives the same fixed
topic input plus concise validation feedback. If no safe draft is available,
the topic receives fallback or insufficient-evidence content.

Each stored topic attempt records the planned `topic_id`, attempt number, raw
response, validation status, validation errors, timing, input size, model
version, prompt version, and contract version. New topic attempts are unique by
report, topic, and attempt number.

## Rendering Contract

Trusted platform code renders:

- the report title;
- one section per planned topic in planned order;
- accepted findings and their citation links;
- a topic-level source list for all qualified topic inputs;
- source-exclusion disclosures;
- `PASS` or `FAIL` grade and reasons;
- fallback evidence briefing when needed.

Citation links point to stored source summaries using the existing
`#summary:<source_ref>` behavior or its validated successor. The model never
supplies navigation targets.

## Failure Contract

The research run fails during reporting only if report inputs cannot be read or
the report package cannot be stored. Model timeout, malformed topic output,
unsupported labels, or unusable findings result in a stored `FAIL` report or
fallback briefing when inputs can be read and stored.
