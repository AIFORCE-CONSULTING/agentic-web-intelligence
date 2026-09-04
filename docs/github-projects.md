# GitHub Projects roadmap connector

The platform can manage draft-only roadmap cards in one GitHub organization
Project. It is intended for authenticated human administrators and operators;
it is not an MCP tool and agents cannot invoke it.

## Scope

The initial connector can:

- read the configured Project's name and `Priority` options;
- list up to 50 draft cards;
- create a draft card with an optional body and `Priority`; and
- update a draft card's existing `Priority` value.

It cannot create repository Issues, Pull Requests, repositories, Project
fields, views, or Projects. The configured Project remains the source of truth.

## Local configuration

Create an organization-owned GitHub Project and add a `Priority` single-select
field. Then set these deployment environment variables locally:

```dotenv
GITHUB_PROJECT_OWNER=AIFORCE-CONSULTING
GITHUB_PROJECT_NUMBER=12
GITHUB_CONNECTOR_TOKEN=replace-with-a-fine-grained-token
```

The token needs the organization's **Projects: Read and write** permission. It
is resolved only through the server-side secret registry and must never be
committed, placed in a browser variable, or pasted into a request. The owner
and Project number are identifiers, not credentials.

Restart the API container after changing `.env`. The Admin page shows safe
configuration status and, once it is ready, the Roadmap panel.

## Guardrails

- A code-owned configuration pins the connector to exactly one organization
  Project.
- Only authenticated human administrators and operators have the
  `github.projects.manage` permission. Service identities and viewers are
  denied.
- Every successful draft creation or Priority update records only the Project
  number, item identifier, and selected Priority in the workspace security
  audit. Titles, notes, and credentials are excluded.
- GitHub provider errors are normalized before returning to the browser; raw
  GitHub responses and the connector token are not exposed.

GitHub's Projects API requires the Projects permission for draft-item creation
and updates. See the [GitHub Projects API documentation](https://docs.github.com/en/rest/projects/drafts).
