# Collaboration instructions

## Design alignment before workflow changes

Before implementing a change that introduces or changes a user action, runtime
workflow, background worker, human approval, durable execution, or external
side effect, present a concise design alignment checkpoint to the user and
wait for explicit approval before editing code.

The checkpoint must explain:

1. what triggers the work;
2. which platform component owns authority and state transitions;
3. where canonical state is stored;
4. whether work runs directly or needs durable execution, and why;
5. how any human decision is recorded and enforced independently of the
   execution mechanism; and
6. which callers or capabilities are explicitly excluded.

Use an ADR when the approved decision creates or changes a lasting architectural
boundary. A pull request verifies the agreed design; it is not the first design
review gate.
