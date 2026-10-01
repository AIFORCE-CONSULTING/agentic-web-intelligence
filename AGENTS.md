# Collaboration instructions

## Design alignment before workflow changes

Before implementing a change that introduces or changes a user action, runtime
workflow, background worker, human approval, durable execution, or external
side effect, first complete an architecture reconciliation, then present a
design alignment checkpoint to the user and wait for explicit approval before
editing code.

### Architecture reconciliation

Inspect the repository before proposing a design. The reconciliation must cite
the relevant existing code and ADRs and explain:

1. which services, routes, workers, workflows, stores, frameworks, and external
   boundaries already address any part of the proposed responsibility;
2. which component owns each responsibility today and which component will own
   it after the change;
3. what will be reused unchanged, extended, adapted, replaced, or retired;
4. whether the proposal would introduce another source of truth, state machine,
   orchestration path, policy implementation, store, or execution mechanism;
5. how the proposal follows the platform's selected frameworks, including
   LangGraph for application orchestration and Temporal for durable execution;
   and
6. how callers and stored state move when existing code is superseded, including
   when the old path can be removed.

For every durable or operator-visible business decision and workflow state, the
reconciliation must also identify the exact canonical record and field, its one
authorized writer, every reader, any derived checkpoint/history/cache, the
complete allowed transitions, and the rule for resolving stale or conflicting
values. Naming only a database or service is insufficient.

Do not add a parallel implementation merely because a roadmap item is phrased
as "add" or "build." Extend the canonical owner unless the user explicitly
approves replacement after reviewing the reconciliation. Any departure from a
selected framework or any new source of architectural authority requires an ADR.

The checkpoint must explain:

1. what triggers the work;
2. which platform component owns authority and state transitions;
3. where canonical state is stored;
4. whether work runs directly or needs durable execution, and why;
5. how any human decision is recorded and enforced independently of the
   execution mechanism; and
6. which callers or capabilities are explicitly excluded.

The checkpoint must include the State and Decision Ownership Matrix required by
the constitution. It cannot be approved while ownership, transitions,
continuation behavior, dependency-failure outcomes, or conflict resolution are
left for implementation tasks to decide.

Use an ADR when the approved decision creates or changes a lasting architectural
boundary. A pull request verifies the agreed design; it is not the first design
review gate.

Follow the repository's [architecture constitution](docs/architecture-constitution.md)
for every design and implementation decision.

<!-- SPECKIT START -->
For significant feature, workflow, authority, durable-execution, human-approval,
or external-effect changes, use the Specify workflow in `.agents/skills/`.
Treat `.specify/memory/constitution.md` as the canonical project constitution.
The active grounded-final-report plan is `specs/003-improve-final-report/plan.md`. Read
`.specify/feature.json` and the selected feature's current specification, plan,
and tasks before implementation. Specify artifacts supplement rather than
replace the architecture reconciliation and approval required above.
<!-- SPECKIT END -->
