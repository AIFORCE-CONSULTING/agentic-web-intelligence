# Governance

Agentic Web Intelligence is maintained as an open-source project with a
deliberate architecture. The goal is to welcome useful community participation
while preserving the platform's local-first, source-grounded, and
policy-controlled design.

## Maintainer Responsibilities

Repository maintainers are responsible for:

- setting project direction and prioritizing roadmap work;
- reviewing and merging pull requests;
- protecting the security, privacy, and supply-chain posture of the project;
- enforcing the [Code of Conduct](https://github.com/AIFORCE-CONSULTING/agentic-web-intelligence/blob/main/CODE_OF_CONDUCT.md); and
- making final decisions when contributors disagree about a change.

Maintainers should explain material decisions in public issues or pull-request
reviews whenever doing so does not expose security-sensitive information.

## How Decisions Are Made

Small corrections, documentation changes, and isolated bug fixes may be decided
in a pull request. Material changes are discussed before implementation.

A material change includes a new or changed user workflow, background worker,
human approval, durable execution behavior, external side effect, authority
boundary, persistent business record, trust-policy rule, or MCP capability.

For those changes, maintainers and contributors should:

1. describe the user problem and expected outcome in an issue or proposal;
2. identify the existing services, stores, workflows, and ADRs involved;
3. agree on the owner of each decision and canonical record before coding; and
4. record a lasting architecture decision in an ADR when appropriate.

For example, a proposal to add a browser-based cookie-consent capability cannot
be treated as a small UI change. It affects external interaction, trust, and
agent authority, so it requires design review and likely an ADR before code is
accepted.

## Contributor Expectations

Contributors are encouraged to bring evidence: reproduction steps, user impact,
alternative approaches, tests, or research. Maintainers may defer a proposal,
request a narrower first step, or reserve it for a future roadmap phase.

An issue labeled `help wanted` indicates that a maintainer believes the work is
scoped well enough for a community pull request. For other substantial changes,
wait for maintainer confirmation before implementation.

## Transparency and Conduct

Public technical decisions belong in issues, discussions, ADRs, or pull-request
reviews. Security reports, personal information, credentials, and other
sensitive material must remain private under the [security policy](https://github.com/AIFORCE-CONSULTING/agentic-web-intelligence/blob/main/SECURITY.md).

Participation in all project spaces is governed by the
[Contributor Covenant Code of Conduct](https://github.com/AIFORCE-CONSULTING/agentic-web-intelligence/blob/main/CODE_OF_CONDUCT.md).
