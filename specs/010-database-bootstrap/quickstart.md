# Quickstart: Database Bootstrap Before Runtime

## Purpose

Use this feature to verify that database schema setup happens before the API
and durable worker process research work.

## Expected Local Flow

1. Start Postgres.
2. Let Docker start the short-lived `database-bootstrap` service, or run
   `python -m app.database_bootstrap` manually in non-Docker tests.
3. Start or restart API and durable worker after bootstrap succeeds.
4. Confirm readiness is healthy and the UI shows a green ready indicator.
5. Run a research workflow.
6. Confirm no schema setup occurs during the research workflow.

## Manual Validation Checklist

- Start from an empty local Postgres volume.
- Bring up the web-research stack with
  `docker compose --profile web-research up -d --build`.
- Confirm the API does not report ready until database bootstrap has completed.
- Confirm the durable worker does not process activities before database
  bootstrap readiness succeeds.
- Confirm the UI shows a green ready indicator only after readiness succeeds.
- Start a research run from the UI.
- Watch API and worker logs during search, preflight, summarization, and report
  generation.
- Confirm no `CREATE TABLE`, `ALTER TABLE`, `DROP CONSTRAINT`, `ADD CONSTRAINT`,
  or `CREATE INDEX` statements are executed during the run.
- Confirm existing research status messages still describe research work, not
  database initialization.

## Failure Validation

- Start API or worker against a database missing required schema.
- Confirm readiness fails with an initialization message.
- Confirm the UI does not show the platform as ready.
- Confirm no research run is marked failed merely because initialization failed.
- Run `python -m app.database_bootstrap`, restart or recheck readiness, and
  confirm research work can proceed.

## Regression Focus

- First-use API request must not initialize schema.
- First-use worker activity must not initialize schema.
- Health checks must not accidentally perform DDL.
- Simultaneous bootstrap attempts must serialize safely.
- Incompatible schema version must report not-ready clearly.
- LangGraph checkpoint setup remains separate from business schema readiness.
- Existing business data survives compatible bootstrap reruns.
