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
keyword counts. The prompt asks the model to choose keywords that the summary
explains, but the platform does not reject an otherwise valid response merely
because the exact keyword phrase is not repeated verbatim in the prose.

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
  "failure_category": "summary_contract_invalid",
  "failure_reason": "The local model could not produce a valid keyword list for this source after two attempts."
}
```

The existing `keyword_coverage` field remains nullable for historical response compatibility but is absent from new summary content.

## Summary Work-Set Read Model

One research task can require more than five relevant sources to be summarized.
The platform groups those sources into internal executions of at most five, then
returns one combined work-set view for the task. This is an operator-facing
progress view, not a second research status and not a new start action.

`GET /v1/research/runs/{run_id}/evidence-summary-work-set` returns the latest
work set for the authenticated workspace member, or a not-found result before
the unified workflow reaches summarization.

```json
{
  "run_id": "uuid",
  "status": "waiting",
  "total_executions": 3,
  "terminal_executions": 2,
  "successful_executions": 1,
  "failed_executions": 1,
  "sources_summarized": 6,
  "sources_failed": 2,
  "failure_summaries": [
    {
      "url": "https://example.org/article",
      "failure_category": "summary_contract_exhausted",
      "failure_reason": "The local model could not create a valid summary after two attempts."
    }
  ]
}
```

The research workspace displays the combined outcome. It never selects the
most recently created internal five-source execution as if that one job were
the complete research task.

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
