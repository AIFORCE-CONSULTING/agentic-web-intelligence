# Durable execution

Phase 5 adds a local Temporal deployment for approved runtime work that must
survive a process restart. It is governed by
[ADR 0013](adr/0013-governed-durable-execution-contract.md).

## Local services

Start the profile with:

```powershell
docker compose --profile durable-execution up -d --build
```

The local Temporal API listens on port `7233`; the Temporal UI is available at
<http://localhost:8233>. The API remains at port `8000` and the web console at
port `3000`.

The profile starts a dedicated `durable-worker` container. It receives only the
database, Temporal, and governed research configuration it needs. It does not
receive the bootstrap-admin secret, OIDC client secret, browser session data,
or GitHub Projects connector token.

## Current boundary

The worker registers exactly one fixed Temporal workflow and two server-owned
activities: approved researcher execution and no-tool review. Each activity
reloads the persisted runtime run and verifies its workspace and current state
before calling the existing runtime service.

There is intentionally no public workflow-start endpoint, MCP tool, agent
credential, or generic Temporal client. Scheduling can only be invoked by
an authenticated human administrator or operator after a runtime plan has
reached its existing approval gate. The control plane exposes two fixed
workspace-scoped actions: schedule that run, and cancel a nonterminal run.
Neither accepts a goal, role, tool, capability, workflow name, or scheduler
credential from the caller. Service identities and viewers cannot invoke them.
