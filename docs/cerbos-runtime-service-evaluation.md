# Cerbos and RuntimeService Evaluation

## Purpose

This evaluation uses the open-source Cerbos authorization model as a benchmark
for the platform's `RuntimeService`. It does not approve replacing
`RuntimeService`, adding a Cerbos dependency, or creating another authorization
path. The immediate question is whether Cerbos documents safeguards that reveal
important gaps in the authority boundary we operate today.

## Conclusion

Do not replace `RuntimeService` or add Cerbos today. `RuntimeService` owns more
than policy evaluation: it also protects workflow transitions, human approval,
bounded retries, role handoffs, and durable-execution state. Cerbos deliberately
answers the narrower question of whether a principal may perform an action on a
resource in the current context.

Cerbos does reveal five practices that should be incorporated into
`RuntimeService` before the new agentic workflow receives live capabilities:

1. authorize a stored actor and action against a stored resource and current
   context, rather than accepting a caller-supplied step object or capability
   grant as proof of authority;
2. attach an explicit authority-policy version to every runtime run and
   authorization decision;
3. return and store a structured decision with an allow-or-deny outcome, stable
   reason code, and safe explanation;
4. record both allowed and denied capability decisions, not only successful tool
   outcomes; and
5. maintain a complete, version-controlled authorization test matrix covering
   every role, action, resource state, and default-deny case.

These improvements preserve the existing authority boundary. They do not
require Cerbos.

## What Cerbos provides

Cerbos is a policy decision point. An application supplies a principal, one or
more requested actions, a resource, and contextual attributes. Cerbos evaluates
versioned policies and returns allow-or-deny decisions. It does not execute the
action.

The following Cerbos practices are relevant to this platform:

- **Default deny:** an action without an explicit allow is denied. See
  [How Cerbos evaluates requests](https://docs.cerbos.dev/cerbos/latest/policies/evaluation.html).
- **Roles plus current context:** policies may use static roles, resource facts,
  principal facts, and request-time conditions. See
  [Conditions](https://docs.cerbos.dev/cerbos/latest/policies/conditions.html).
- **Typed policy inputs:** JSON schemas can reject malformed principal and
  resource attributes before policy evaluation. See
  [Schemas](https://docs.cerbos.dev/cerbos/latest/policies/schemas.html).
- **Versioned policies:** resource and principal policies can have multiple
  versions, and requests identify the applicable version. See
  [Resource policies](https://docs.cerbos.dev/cerbos/latest/policies/resource_policies.html).
- **Explainable decisions:** evaluation metadata can identify matched policies,
  and rule outputs can provide application-readable reasons. See
  [Debugging authorization decisions](https://docs.cerbos.dev/cerbos/latest/policies/debugging.html)
  and [Outputs](https://docs.cerbos.dev/cerbos/latest/policies/outputs.html).
- **Decision auditing:** Cerbos can retain access and decision logs and gives
  each evaluated call an identifier that an application can retain in its own
  audit trail. See
  [Audit configuration](https://docs.cerbos.dev/cerbos/latest/configuration/audit.html).
- **Policy tests:** policy repositories can be compiled and tested in CI using
  cases organized by principal, resource, and action. See
  [Validating and testing policies](https://docs.cerbos.dev/cerbos/latest/policies/compile.html).

## What RuntimeService already does well

The current `RuntimeService` contains important protections that must not be
lost:

- roles and capabilities are assigned by platform code, not proposed by the
  model;
- only the researcher role receives `web.search` and `web.extract`;
- planner and reviewer roles have no web capability;
- a run must reach the correct stored state before a step can activate;
- execution requires a recorded human approval;
- human-facing API operations require an authenticated human with the relevant
  workspace permission;
- handoffs are restricted to approved role relationships;
- reviewer revisions and operator-approved exception revisions are bounded;
- ambiguous durable work stops for attention instead of being retried as if its
  outcome were known;
- runtime runs, steps, events, handoffs, and bounded memory are retained in
  PostgreSQL; and
- unknown capabilities are denied because they are absent from the stored step
  grant.

Cerbos does not replace these workflow and human-authority responsibilities.

## Important gaps revealed by the comparison

### 1. Capability authorization trusts too much caller-supplied state

`RuntimeService.authorize_capability` currently receives a `RuntimeStep` object
and checks whether a capability name appears in that object's
`allowed_capabilities` list. It does not reload the step and run from the
canonical store or independently confirm:

- that the step belongs to the requested run and workspace;
- that the step is currently active;
- that the run is in a state where the action is allowed;
- that the requested resource belongs to the task; or
- that the supplied arguments remain inside the task's limits.

Trusted callers reduce today's exposure, but the new LangGraph nodes must not be
able to authorize themselves by constructing or passing capability collections.

**Recommendation:** replace the object-based check with a request containing
stable identifiers and bounded facts: workspace, run, step, action, resource,
and safe context. RuntimeService must load the canonical role, grants, and state
before deciding.

### 2. Authority policy has no explicit recorded version

The role grants, timeouts, handoffs, and limits are version-controlled source
constants, but a runtime run or capability decision does not identify which
authority-policy version was applied. Later code changes can therefore make an
old decision difficult to explain precisely.

**Recommendation:** define one authority-policy version and store it with each
run and authorization decision. A changed rule set receives a new version.
Historical runs continue to identify the version under which they were
authorized.

### 3. Capability decisions are not structured or fully audited

The current authorization method returns nothing when allowed and raises a
general exception when denied. Successful tool outcomes can be recorded later,
but authorization decisions themselves are not represented by a durable record
containing the action, safe resource facts, outcome, reason, and policy version.

**Recommendation:** return a typed decision such as `allow` or `deny` with a
stable reason code and human-readable explanation. Persist both allowed and
denied decisions before any allowed tool is executed. Exclude secrets and raw
page content from the record.

### 4. Capability checks lack resource and request context

Membership in a role's capability list answers whether a researcher may ever
request `web.extract`; it does not answer whether this researcher may extract
this URL for this task at this time. The newer research-control code separately
checks discovered URLs, duplicate queries, source attempts, and gap-search
limits, which is why it began to overlap RuntimeService.

**Recommendation:** preserve those useful checks but place their authority under
RuntimeService. The authorization request should include bounded context needed
to verify source scope, task limits, current stage, and any required human
decision. LangGraph may propose the action but may not provide its own grant.

### 5. Tests do not form one complete authority matrix

The repository has meaningful tests for plans, human gates, handoffs, retries,
workspace access, and durable execution. They are distributed across service,
route, and workflow tests. There is no single matrix demonstrating that every
role is allowed or denied for every protected action and relevant resource
state.

**Recommendation:** add a versioned authorization test matrix. At minimum it
must cover every role against every capability, unknown roles and capabilities,
inactive or terminal steps, wrong-workspace and wrong-run resources,
undiscovered URLs, exhausted limits, missing human approval, and malformed
authorization context. Every unspecified combination must demonstrate default
deny.

## Cerbos features not needed now

The following Cerbos features are valuable in larger authorization estates but
do not solve an immediate platform gap:

- dynamically derived roles;
- per-principal policy overrides;
- hierarchical policy scopes;
- policy hot-loading or administrative policy APIs;
- externally managed decision-log storage;
- authorization query plans for filtering large collections; and
- a separately deployed policy decision service.

Introducing these now would increase local operating complexity without fixing
the current integration problem between LangGraph and RuntimeService.

## Recommendation

Keep RuntimeService as the platform's single agent-authority and workflow-state
boundary. Improve it using the five practices above, then connect the unified
LangGraph through that strengthened boundary. Move the unique source-scope and
budget checks from `AgenticResearchControlService` beneath RuntimeService and
remove the competing authority path once callers and stored records have been
migrated safely.

Continue monitoring Cerbos. Reconsider using it as the policy evaluator behind
RuntimeService when the platform has substantially more roles, tools, resource
types, tenant-specific policies, or policy changes that must be managed
independently of application releases.

