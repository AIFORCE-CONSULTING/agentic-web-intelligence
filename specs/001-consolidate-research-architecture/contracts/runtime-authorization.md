# Contract: Runtime Authorization

Every model-proposed capability crosses `RuntimeService` before the governed MCP
host executes it.

## Request

Required: workspace, runtime run and step, research task, workflow stage,
action, resource type and stable ID, bounded typed arguments,
request/idempotency ID, and purpose when applicable. Roles, grants, trust
decisions, human approvals, and counters are absent and reloaded from stores.

## Decision

Persist and return `allow` or `deny`, stable reason code, safe explanation,
authority-policy version, bounded redacted facts, decision identity, and time.

## Sequence

1. Validate shape and action.
2. Load run and step.
3. Check active state, workspace, and task relationship.
4. Check stored grant and workflow stage.
5. Check resource ownership and discovered-source scope.
6. Transactionally enforce query, source, attempt, retry, and gap limits.
7. Read bounded trust/human facts only when required; never duplicate policy.
8. Persist the decision.
9. Immediately before provider invocation, reload or atomically verify the
   current workspace, research task and status version, assignment, step,
   request, action/tool, resource, and applicable limits. A changed fact makes
   the prior allow decision stale and execution fails closed with a recorded
   denial or conflict.
10. Pass the stored authorization decision identity and its bounded correlation
   fields to the governed MCP host.
11. Permit MCP execution only when the host verifies that workspace, research
    task, runtime run, runtime step, request, action/tool, and resource match the
    stored allow decision.
12. Persist the MCP execution audit with those identities and the normalized
    outcome.

Anything unknown, missing, inactive, out of scope, malformed, or exhausted is
denied. Model output and graph state cannot override the result.

For every agent-triggered MCP call, the execution audit requires:

- `workspace_id`;
- `research_run_id`;
- `runtime_run_id`;
- `runtime_step_id`;
- `authorization_decision_id`;
- `request_id`;
- `tool_name`;
- bounded `resource_type` and `resource_id` when applicable;
- normalized `outcome`; and
- `occurred_at`.

These fields must describe the same allowed request. Missing or inconsistent
correlation fails closed before provider invocation. Non-agent MCP calls use
their existing human or platform attribution and cannot imitate an agent
authorization decision.

If PostgreSQL is unavailable, RuntimeService cannot establish authority or
persist a decision, so execution is denied and the caller receives a typed
service-unavailable error. A caller-provided assignment, cached decision, graph
checkpoint, or Temporal payload cannot substitute for stored authority.
