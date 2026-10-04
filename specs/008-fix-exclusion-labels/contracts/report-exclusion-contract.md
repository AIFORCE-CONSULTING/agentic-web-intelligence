# Contract: Report Exclusion Reasons

The existing report response includes `exclusions` under:

`GET /v1/research/runs/{run_id}/report`

This feature preserves the existing response shape and tightens the meaning of
`reason_code` and `reason`.

## Response Shape

```json
{
  "exclusions": [
    {
      "title": "Beyond Ollama: Faster Local LLM Serving, Real Concurrency, and ...",
      "url": "https://example.test/source",
      "topic_ids": ["ollama-concurrency"],
      "reason_code": "access_denied_by_publisher",
      "reason": "The publisher or website rejected automated access before usable evidence could be captured."
    }
  ]
}
```

## Allowed Reason Codes

| Reason code | Meaning |
| --- | --- |
| `blocked_by_trust_policy` | The local trust workflow blocked the source before report use. |
| `review_required` | Human review was required and no current acceptance allowed automated use. |
| `access_denied_by_publisher` | The source rejected automated access before usable evidence was captured. |
| `unreachable` | The platform could not capture usable evidence for another reason. |
| `summary_failed` | Evidence was captured, but summary processing did not store a usable summary. |
| `evidence_insufficient` | Captured content was insufficient for report findings. |
| `not_relevant_to_planned_topics` | Usable summarized evidence existed, but it did not qualify for any planned topic in this report. |

## Compatibility

- The response shape remains compatible with the current UI.
- Existing historical reports keep their stored reason codes and reason text.
- New reports should use the refined reason codes.
