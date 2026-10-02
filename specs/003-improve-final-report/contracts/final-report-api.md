# Final Report API and UI Contract

## Existing endpoint extended

GET /v1/research/runs/{run_id}/report remains the only report read endpoint. It requires the existing research.read permission and never starts model work.

A successful response adds report identity, contract version, currentness, supporting-source mapping, and exclusions to the current report fields.

    {
      "id": "4ea1163b-4e45-45bf-98c9-5f52e42fc66d",
      "run_id": "8aaeac36-8851-4f96-b2ea-f84e217b8307",
      "markdown": "## Topic: Agentic-web technologies\\n...",
      "model_name": "qwen3:1.7b",
      "prompt_version": "agentic-research-final-report-v2",
      "contract_version": "grounded-final-report-v1",
      "quality_grade": "FAIL",
      "quality_reasons": [
        {"code": "narrative_length", "message": "The narrative did not meet the 1,200-word target."}
      ],
      "report_origin": "model_fail",
      "current": true,
      "supporting_sources": [
        {"source_ref": "source-01", "topic_id": "agentic-web-technologies",
         "title": "A practical WebMCP example", "url": "https://example.test/webmcp"}
      ],
      "exclusions": [
        {"title": "Related but off-topic article", "url": "https://example.test/off-topic",
         "topic_ids": ["agentic-web-technologies"], "reason_code": "not_relevant",
         "reason": "Assessed for Agentic-web technologies: recorded relevance outcome was not relevant to this topic."}
      ]
    }

A 404 means no stored report package exists. A stale historical report is never rendered as a current report. quality_reasons is an ordered list of code and message objects. Its codes are missing_topic_coverage, unrepresented_qualified_source, narrative_length, model_unavailable, malformed_model_response, and unsafe_model_draft. report_origin is one of model_pass, model_fail, or fallback. The response always distinguishes the research workflow result from the report-quality grade. A `FAIL` quality grade means the report did not satisfy one or more completeness, traceability, structure, or detail checks; it does not mean the stored evidence failed trust policy and it does not make the completed research run failed.

## Structured model draft

Ollama receives a native JSON schema. The model returns topic sections, findings with known source_refs, section source references, and explicit supported or insufficient evidence status. It does not return URLs, HTML, Markdown links, exclusions, eligibility, or completion status.

The server checks missing topics, unknown or wrong-topic source references, sources not represented in a section, uncited factual findings, findings in insufficient sections, and an applicable word-target failure. A passing draft becomes a `PASS` report. After one correction, only a schema-valid draft whose every factual finding has a known topic-scoped source reference and has no findings in insufficient sections may become a `FAIL` report. The platform selects the safe draft with the most passed checks across topic coverage, source representation, and narrative length; a tie selects attempt two. If no model draft is safe, the platform creates a fallback evidence briefing from the fixed input with a `FAIL` grade and a specific fallback reason code.

## UI behavior

- The Final report panel remains in its current location.
- Platform-generated attribution and source-list links select the existing stored summary; they never fetch a public website.
- Exclusions are clearly separate from report-supporting sources.
- The Markdown renderer accepts only platform-generated stored-summary links.
- A run reporting status shows preparation. A completed run shows the report quality badge and its reasons. The research workflow fails during reporting only when the platform cannot read report inputs or store the report package.
