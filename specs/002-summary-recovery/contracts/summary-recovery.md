# Contract: Summary Recovery and Report Read Model

## Model Response Contract

### Chunk summary

```json
{
  "summary": "A factual summary of this bounded source chunk.",
  "keywords": ["three", "to", "five specific terms"]
}
```

### Completed source summary

```json
{
  "summary": "A complete evidence-grounded source summary.",
  "keywords": ["three", "to", "seven specific terms"],
  "evidence_sufficient": true
}
```

Chunk and consolidation responses contain only `summary` and `keywords`. Final
source responses additionally contain `evidence_sufficient`. The platform
rejects extra fields, invalid JSON, blank or duplicate keywords, out-of-range
keyword counts, and keywords not found in the normalized summary.

For keyword presence, the platform trims outer whitespace, collapses repeated
internal whitespace to one space, compares case-insensitively, preserves
punctuation, and requires the complete normalized keyword phrase to occur in
the normalized summary.

`evidence_sufficient: false` means the final response satisfied the output
contract but the source material does not support a complete, reliable briefing.
The source remains visible as completed, but the platform excludes it from
topic coverage and report input. It is not retried as a malformed response.

## Corrective Request Contract

The one permitted corrective request contains the original fixed instructions, the same bounded source-derived input, and a platform-created validation category. It asks for a complete replacement response. It does not include raw prior output, database state, credentials, tool descriptions, or authority decisions.

## Summary Execution Read Model

The existing summary-execution response adds these nullable source fields:

```json
{
  "url": "https://example.org/article",
  "status": "failed",
  "summary_attempt_count": 2,
  "failure_category": "keyword_absent_from_summary",
  "failure_reason": "The local model could not produce a valid keyword list for this source after two attempts."
}
```

The existing `keyword_coverage` field remains nullable for historical response compatibility but is absent from new summary content.

## Safe Source-Failure Presentation

The existing summary-execution response uses the shared category and fixed
operator message defined in the feature data model. The UI displays this safe
message with the source status. It does not display raw model output, prompts,
worker logs, credentials, or provider configuration.

## Final Report Read Contract

`GET /v1/research/runs/{run_id}/report` returns the one stored report for an authenticated workspace member, or a not-found result when the task has not reached report completion.

```json
{
  "run_id": "uuid",
  "markdown": "# Executive report\n...",
  "model_name": "local-model-name",
  "prompt_version": "agentic-research-final-report-v1",
  "created_at": "2026-09-29T00:00:00Z"
}
```

The route is read-only. It does not run a model, retry a failed summary, alter research status, or expose failed raw model output.
