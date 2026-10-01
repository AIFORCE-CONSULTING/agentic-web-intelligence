# Research Notes: Reliable Summary Recovery

## Simplify the model output contract

The local model will return a summary and a list of keywords. It will no longer return `keyword_coverage`, a second model-generated structure that maps each keyword to a supporting sentence.

The evidence-summary service will normalize case and whitespace and verify that every keyword occurs in the summary. It will also require unique, non-empty keywords and the feature's bounded keyword counts.

**Rationale**: The live failure was valid JSON whose two independently generated keyword structures did not agree. Removing the map makes the prompt and schema simpler while retaining the business rule that a stored keyword cannot be unrelated to its summary.

**Rejected alternative**: Keep the coverage map and add retries. This would mask a fragile, redundant contract rather than remove its main source of failure.

## Retry only a completed but invalid model response

Each summary unit receives at most two completed model responses: the initial response and one corrective replacement response. A unit is a source chunk, a bounded consolidation group, or a final source summary.

The corrective request uses the same fixed instructions and source-derived input. It adds only a safe typed explanation of the failed rule, such as invalid JSON, missing required field, invalid keyword count, duplicate keyword, or keyword absent from summary. It requests a complete replacement, never an edit to the invalid output.

**Rationale**: A second attempt handles occasional local-model formatting mistakes without allowing an unbounded repair loop or broadening model authority.

**Rejected alternative**: Treat a provider connection failure as the corrective attempt. No response exists to validate, so it remains a dependency failure governed by the existing direct or Temporal execution path.

## Preserve valid sources when one source exhausts recovery

When a summary unit exhausts its two valid-response attempts, the evidence-summary service marks only that source as failed and continues with remaining sources. An execution completes when at least one source has a valid final source summary. If no eligible, relevant source has a valid final summary, the execution fails and the unified research workflow does not generate a report.

**Rationale**: One source-level model-formatting failure must not discard valid work from other sources. Topic coverage and reporting already select accepted summary artifacts only.

## Record safe attempt diagnostics, not raw model output

The evidence-summary store will retain one append-only attempt record for each accepted or rejected completed model response. It records the execution, source version, summary-unit identity, attempt number, outcome, safe validation category, prompt version, model version, and timestamp. It does not retain raw model output, evidence text, hidden instructions, credentials, or provider configuration.

**Rationale**: Operators need to distinguish a model-contract failure from extraction, trust, or service failures. The platform does not need to retain untrusted malformed content merely to explain the outcome.

## Make omissions explicit without letting the model decide disclosure

The final-report service receives qualified summaries only. If sources exhaust summary recovery, trusted platform code adds a deterministic omitted-sources notice to the stored report. The notice gives the number of omitted sources and safe source-level failure details.

The existing Research workspace will show failed sources and their safe reason in its summary-status area and add a read-only Final report section for the report already stored by the agentic-research reporting service.

## Keep existing architectural owners

| Responsibility | Existing owner retained | Change |
| --- | --- | --- |
| Summary output contract and validation | `EvidenceSummaryService` | Extend it with keyword-presence validation and one corrective response. |
| Summary execution and source status | `EvidenceSummaryStore` | Extend it with attempt diagnostics and source failure details. |
| Direct versus durable routing | `EvidenceSummaryAutomation` and Temporal boundary | Reuse unchanged; recovery is internal to one execution. |
| Workflow continuation and official research status | Unified LangGraph workflow and `ResearchStore` | Reuse unchanged; it receives a completed or failed summary execution outcome. |
| Agent authority and capability grants | `RuntimeService` | Reuse unchanged; the summarizer receives no capabilities or authority. |
| Evidence eligibility and human acceptance | Web-trust and evidence-review services | Reuse unchanged before summary recovery starts. |
| Final report storage | `AgenticResearchStore` | Extend report composition with a deterministic omission notice and expose the stored report read-only. |

## References

- `apps/api/app/evidence_summaries/service.py`
- `apps/api/app/evidence_summaries/store.py`
- `apps/api/app/evidence_summaries/workflow.py`
- `apps/api/app/agent_runtime/research_workflow.py`
- `apps/api/app/agentic_research/reporting.py`
- `docs/adr/0014-governed-local-model-provider.md`
- `docs/adr/0016-governed-local-agent-capability-requests.md`
