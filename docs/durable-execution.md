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
activities: approved researcher execution and no-tool review. Human approval is
recorded by the runtime service before any execution path is selected. Trusted
platform code may then choose the durable workflow only for work that needs it.
Each activity reloads the persisted runtime run and verifies its workspace and
current state before calling the existing runtime service.

There is intentionally no public workflow-start endpoint, MCP tool, agent
credential, or generic Temporal client. Scheduling can only be invoked by
trusted server-side platform code after a runtime plan has recorded human
approval. An authenticated human administrator or operator approves or rejects
the known workspace-owned run through the runtime control plane; that decision
does not start, signal, or configure Temporal. Durable cancellation remains a
human control for a run that trusted code has already scheduled. No action
accepts a goal, role, tool, capability, workflow name, or scheduler credential
from the caller. Service identities and viewers cannot invoke them.

## Operator visibility

The Admin console's **Durable work** section is available to authenticated
administrators and operators. It lists only the current workspace's stored run
state, approval decision, approved steps, bounded lifecycle events, and the
fixed actions that are currently legal. It does not display raw Temporal
histories, workflow IDs, credentials, or cross-workspace data.
