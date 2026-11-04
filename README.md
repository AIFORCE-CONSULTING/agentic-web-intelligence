# Agentic Web Intelligence

Agentic Web Intelligence is a local-first, source-grounded research platform.
It helps an operator turn a question into governed web research: the platform
discovers sources, evaluates whether evidence is safe and useful to use,
preserves evidence and its provenance, and builds a traceable research wiki for
each topic.

The platform is designed to make credible research available without requiring
cloud-model access or an expensive research subscription.

## What It Does

- Creates durable **Research Topics** that collect related questions, evidence,
  source summaries, keywords, and immutable wiki revisions over time.
- Uses LangGraph to coordinate one research workflow and Temporal for work that
  needs durable execution. The operator starts research once; the platform
  selects the execution path automatically.
- Keeps web search and extraction behind a governed MCP host. Models may request
  approved capabilities, but cannot directly use a browser, shell, database,
  credentials, or arbitrary network tools.
- Applies a local web-trust policy before evidence reaches a model. The platform
  preserves retrieval facts and decisions, blocks unsafe evidence, and requires
  a recorded human decision for evidence that needs review.
- Uses a local Ollama model for bounded semantic work: topic planning,
  relevance decisions, summaries, keywords, and source-grounded wiki findings.

## Quick Start

The shortest path to a working local platform is documented in the
[Quickstart](docs/quickstart.md). In outline:

1. Install Docker Desktop and [Ollama](https://ollama.com/), then pull the
   local model: `ollama pull qwen3:1.7b`.
2. Copy `.env.example` to `.env` and replace every sample secret.
3. Start the full local research platform:

   ```powershell
   docker compose --profile web-research up -d --build
   ```

4. Open the Research Workspace at `http://localhost:3000/` and documentation at
   `http://localhost:8001/`.

The platform remains local by default. Do not expose a development deployment
to the public internet.

## Documentation

- [Documentation site](https://aiforce-consulting.github.io/agentic-web-intelligence/)
- [Current platform architecture](docs/current-platform-architecture.md)
- [Architecture decisions](docs/decisions.md)
- [Roadmap](ROADMAP.md)
- [Local Evidence Intelligence](docs/local-evidence-intelligence.md)
- [Contribution guide](CONTRIBUTING.md)

## Contributing and Community

This project welcomes bug reports, documentation improvements, research
findings, and carefully scoped code contributions. Please read
[CONTRIBUTING.md](CONTRIBUTING.md) before beginning work. Community conduct is
governed by [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md), and the maintainer decision
process is described in [GOVERNANCE.md](GOVERNANCE.md).

For help, bugs, feature proposals, and security reporting, see
[SUPPORT.md](SUPPORT.md). Do not report security vulnerabilities in public
issues or pull requests.

## License

Copyright 2026 Agentic Web Intelligence contributors. Licensed under the
[Apache License 2.0](LICENSE).
