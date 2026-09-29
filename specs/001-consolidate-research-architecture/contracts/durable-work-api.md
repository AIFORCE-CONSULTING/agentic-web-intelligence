# Contract: Consolidated Research Durable-Work API

## `GET /v1/research/durable-work`

This replacement read-only endpoint supplies the Admin **Durable work** section.
Results are restricted to the authenticated administrator or operator's
workspace.

Each item identifies the research run, research question, current canonical
research status, operation type, selected route (`direct` or `temporal`), stored
operation status, last update time, and bounded failure code or safe explanation
when present.

The API composes this response from `ResearchStore` and the existing
candidate-preflight and evidence-summary owning stores. It does not create a new
durable-work table and does not translate Temporal history into application
status.

## `GET /v1/research/runs/{run_id}/durable-work`

The detail response includes the same workspace-owned research identity and a
bounded list of its durable operations. Each operation links to its owning
application record. Raw evidence, prompts, model output, credentials, and raw
Temporal event history are excluded.

## Controls

Consolidated research entries are read-only in this Admin section. Human
evidence acceptance continues through the evidence-review API and UI.

The old `/v1/runtime/runs` list, detail, approval, attention, and cancellation
contracts retire with `GovernedRuntimeWorkflow`. No compatibility response or
legacy-data migration is required.

## Errors

- `401` or `403` for unauthenticated or unauthorized callers;
- `404` when the workspace-owned runtime/research record does not exist; and
- `503` when an owning PostgreSQL store cannot build the read model.

The endpoint never falls back to Temporal as the business record.
