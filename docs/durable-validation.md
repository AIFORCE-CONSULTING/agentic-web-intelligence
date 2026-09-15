# Durable execution validation

This guide validates the Phase 5 control boundaries without adding a public
runtime-start route or an agent-accessible Temporal capability.

## Automated coverage

Run the API suite from the repository root:

```powershell
docker run --rm -v "${PWD}:/workspace" -w /workspace/apps/api python:3.12-slim sh -lc "pip install --require-hashes --only-binary=:all: -r requirements-dev.lock && ruff check . && PYTHONPATH=/workspace/apps/api pytest -q"
```

The durable-execution tests verify that:

- a recovered activity revalidates the stored workspace and policy version;
- a cancelled run stops before a new research-tool call;
- uncertain activity outcomes become `needs_attention` without retrying;
- the fixed durable workflow performs at most three routine researcher
  attempts; and
- viewers cannot exercise runtime execution authority.

The runtime tests also verify the three normal researcher attempts and the
separate three-decision operator exception budget.

## Local operational checks

Start the standard local platform profile:

```powershell
docker compose --profile web-research up -d --build
```

Confirm the API is healthy, the worker is running, and Temporal is available:

```powershell
docker compose --profile web-research ps
```

Temporal's local operator UI is available at <http://localhost:8233>. It is
operational visibility only; runtime state, approval records, and workspace
authorization remain in PostgreSQL and the platform's Admin console.

## Manual operator review

When a trusted server-side integration creates an approved durable run, sign in
to <http://localhost:3000/admin> as an administrator or operator and inspect
the workspace-owned record.

- A cancelled run must not start another researcher or reviewer activity after
  its persisted cancellation checkpoint.
- A review that exhausts its three routine attempts displays `needs_attention`.
  Only an authorized operator can approve an exception revision, up to three,
  or close the work.
- A `needs_attention` record caused by an ambiguous durable activity has no
  revision action. It must be closed or handled through a later, explicit
  recovery design.
- A record from another workspace must never appear or be controllable.

No test or operational step should use an MCP tool, browser request, or agent
instruction to create, schedule, or alter a runtime run.
