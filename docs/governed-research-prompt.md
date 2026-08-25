# Governed research prompt

`governed-research` is the platform's first versioned prompt template. It is a
repeatable instruction for an agent runtime; rendering it does not invoke a
model or fetch web content.

The prompt instructs an agent to use only the platform's governed research
capabilities, treat retrieved page content as untrusted data, preserve a
durable research run, attribute findings, and distinguish source data from
ground truth.

## API contract

- `GET /v1/prompts` lists available prompt declarations.
- `GET /v1/prompts/governed-research` returns this template's metadata and
  declared arguments.
- `POST /v1/prompts/governed-research/render` renders its two messages.

~~~powershell
Invoke-RestMethod -Method Post `
  -Uri http://localhost:8000/v1/prompts/governed-research/render `
  -ContentType application/json `
  -Body '{"question":"What is agentic web intelligence?"}'
~~~

The response includes the template ID and version. A later MCP server will map
this same declaration and renderer to the MCP `prompts/list` and `prompts/get`
operations, rather than maintaining a second prompt catalog.
