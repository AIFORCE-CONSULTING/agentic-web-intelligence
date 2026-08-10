# Style Guide

## Documentation

- Explain both the implementation and the reason for the decision.
- Prefer concise, active language and task-oriented headings.
- Keep diagrams and ADRs in version control.
- Use source links and retrieval metadata for web-derived claims.

## Python

- Use type hints for public interfaces.
- Keep framework code at the edges; put domain logic in testable modules.
- Prefer explicit configuration and dependency injection over global state.

## React and TypeScript

- Use TypeScript in strict mode.
- Build accessible, composable components.
- Keep network and stateful logic outside presentational components.
- Display source provenance and uncertainty in agent-facing interfaces.
- Pin direct npm dependencies to exact approved versions; review and commit every lockfile change.
- Disable dependency lifecycle scripts by default and approve any exception explicitly.
