# Quickstart: Verify Topic-Scoped Final Reports

## Goal

Confirm the final report is assembled from planned topics and topic-scoped
source summaries, while the local model only drafts bounded findings for one
topic at a time.

## Manual Verification

1. Start the local stack with API, worker, web, database, Temporal, SearXNG, and
   Ollama available.
2. Configure the local model provider for the workspace.
3. Purge or use a clean research run if historical data would confuse the test.
4. In the UI, enter a research question that produces multiple planned topics.
5. Select the desired source count and run Discover Sources.
6. Wait for the workflow to complete through report generation.
7. Open the Final report panel.
8. Confirm the report contains one section per planned topic in the planned order.
9. Confirm citation labels are simple labels such as `S01` and link to stored
   source summaries.
10. Confirm each topic includes a source list even when not every source appears
    in a finding citation.
11. Confirm exclusions remain separate from supporting evidence.
12. Confirm the report shows a `PASS` or `FAIL` quality grade with concise reasons.

## Failure Verification

1. Use fixtures or a mocked local-model response that cites an unsupported source
   label.
2. Confirm the unsupported label is rejected and does not appear as a working
   citation in the report.
3. Use fixtures or a mocked response that includes legacy or unexpected
   model-authored topic fields.
4. Confirm those topic fields are ignored or rejected and the stored planned
   topic list still defines the rendered report sections.
5. Simulate an unavailable model or timeout.
6. Confirm the operator receives a fallback evidence briefing rather than an
   absent report, provided report inputs can be read and stored.

## Automated Verification

Run focused API reporting tests covering:

- planned-topic section rendering;
- `S01`-style source-label assignment;
- harmless citation-label normalization;
- unsupported label rejection;
- legacy or unexpected model-authored topic field rejection;
- topic-specific fallback behavior;
- report package persistence and currentness;
- existing report endpoint behavior.

Then run the normal API lint/test suite and web build before opening a PR.

Current verification commands:

```powershell
docker run --rm -v "${PWD}:/workspace" -w /workspace/apps/api python:3.12-slim sh -lc "pip install --require-hashes --only-binary=:all: -r requirements-dev.lock >/dev/null && ruff check . && PYTHONPATH=/workspace/apps/api pytest -q"
```

```powershell
Push-Location apps/web
npm run build
Pop-Location
```

```powershell
git diff --check
```
