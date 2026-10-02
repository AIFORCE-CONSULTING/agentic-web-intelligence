# Quickstart: Verify Grounded Final Reports

## Operator verification

1. Start the existing local platform and local Ollama provider.
2. Run the normal Discover Sources workflow for a question that produces at least ten eligible, relevant, evidence-sufficient summaries across two or more topics.
3. Wait for research_runs.status to become completed.
4. Confirm Final report contains a labeled section for every planned topic and a visible PASS or FAIL quality grade.
5. Select a claim attribution and confirm it opens the stored source summary, not the public site.
6. Confirm each topic has a complete linked supporting-source list.
7. Confirm exclusions are separate and explain the assessed topic and recorded reason.
8. For ten or more qualified sources, confirm the narrative is approximately 1,200-1,800 words excluding lists and exclusions.

## Recovery verification

1. Use a fixture where the first model response omits a topic or source reference.
2. Confirm attempt one is stored as rejected with validation detail.
3. Confirm exactly one correction call uses the same input fingerprint.
4. If attempt two passes, confirm the report receives a PASS quality grade.
5. If attempt two fails but is parseable, confirm the best usable report is visible with a FAIL quality grade and concise reasons.
6. If Ollama is unavailable or both attempts are unusable, confirm a clearly labeled fallback evidence briefing is visible with a FAIL quality grade.
7. Confirm the research run fails during reporting only when the platform cannot read the report inputs or store the report package.

## Automated verification

Add focused API tests for schema validation, source mapping, exclusions, attempt persistence, status transitions, wrong-workspace access, retry/idempotency, stale inputs, and safe link rendering. Run the existing API test suite and web build.
