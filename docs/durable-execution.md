# Durable execution

Phase 5 adds a local Temporal deployment for approved runtime work that must
survive a process restart. It is governed by
[ADR 0013](adr/0013-governed-durable-execution-contract.md).

## Local services

Start the standard local platform profile with:

```powershell
docker compose --profile web-research up -d --build
```

The local Temporal API listens on port `7233`; the Temporal UI is available at
<http://localhost:8233>. The API remains at port `8000` and the web console at
port `3000`.

The standard profile starts a dedicated `durable-worker` container. It receives only the
database, Temporal, and governed research configuration it needs. It does not
receive the bootstrap-admin secret, OIDC client secret, browser session data,
or GitHub Projects connector token.

The `durable-execution` Compose profile remains available for focused
durable-runtime development and validation. It is not required to enable
durable routing in the normal local platform: `web-research` already includes
Temporal and the worker.

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

Routine reviewer feedback remains automatic and bounded: the approved
researcher/reviewer pair can complete three total researcher attempts. When
that budget is exhausted, the stored run waits in `needs_attention`. An
authenticated administrator or operator can inspect it and approve up to three
exception revisions from the Admin console. Each approval is recorded before
execution resumes and reuses the original plan, roles, workspace, and tools.
It does not start or signal Temporal. An ambiguous durable outcome is not
eligible for this path; it can only be closed or cancelled.

## Operator visibility

The Admin console's **Durable work** section is available to authenticated
administrators and operators. It lists only the current workspace's stored run
state, approval decision, approved steps, bounded lifecycle events, and the
fixed actions that are currently legal. It does not display raw Temporal
histories, workflow IDs, credentials, or cross-workspace data.

## Recovery behavior

Every durable activity reloads the stored run and revalidates the workspace and
policy version before it can act, so a replacement worker does not resume from
untrusted in-memory state. A cancellation already recorded in the runtime store
returns `cancelled` before a new researcher or reviewer call begins. Activity
retries are limited to one attempt. If an activity result is uncertain, the
workflow records only the typed reason `ambiguous_activity_outcome`, transitions
the run to `needs_attention`, and does not retry it automatically.
