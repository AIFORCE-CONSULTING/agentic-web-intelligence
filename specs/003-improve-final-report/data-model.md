# Data Model: Grounded Final Reports

## Existing authoritative records

| Record | Purpose | Owner |
| --- | --- | --- |
| research_runs | Official report-stage progress and failure state | ResearchStore through unified LangGraph wrapper |
| agentic_research_topics | Planned topics and ordering | AgenticResearchStore |
| agentic_topic_coverage_evidence | Qualified source/topic association | Existing coverage workflow |
| evidence_summary_artifacts | Stored summary and keywords | Evidence-summary store |
| web_evidence_trust_evaluations and overrides | Eligibility and human acceptance facts | Web-trust/review stores |
| agentic_research_reports | Accepted operator-facing report | AgenticResearchStore |

## Accepted report extension

Keep agentic_research_reports append-only. Add contract_version, input_fingerprint, quality_grade, quality_reasons, and report_origin. Every stored report package is operator-visible: a passing model report, the best usable incomplete model report, or a platform fallback evidence briefing. The fields record platform-rendered Markdown, model name when available, prompt/contract versions, input fingerprint, grade, reasons, origin, and creation time.

quality_reasons is an ordered JSON array of objects with code and message fields. Its allowed codes are missing_topic_coverage, unrepresented_qualified_source, narrative_length, model_unavailable, malformed_model_response, and unsafe_model_draft. report_origin is the fixed enum model_pass, model_fail, or fallback.

## New immutable report inputs

Create agentic_research_report_inputs, child rows of a stored report.

| Field | Meaning |
| --- | --- |
| report_id | Parent stored report |
| topic_record_id, topic_id | Qualified planned topic |
| summary_artifact_id | Summary record at report time |
| source_ref | Stable internal reference used by draft and renderer |
| source_url, source_title | Operator-facing identity snapshot |
| summary_text, summary_digest | Exact summary provided to model |
| content_hash, position | Evidence identity and stable order |

A source can appear once per qualifying topic. These rows record what the report used; they do not make a new eligibility decision.

## New contribution records

Create agentic_research_report_contributions with report_id, topic_record_id, finding_position, source_ref, and contribution_kind (finding or section_source_list). A `PASS` report requires every qualified input to contribute at least once and each factual finding to have at least one source. A structurally safe `FAIL` report may omit qualified-source contributions, but its quality reasons must name that failed check and its complete frozen input list remains available to the operator.

## New exclusion disclosures

Create agentic_research_report_exclusions with report_id, source identity, assessed topic_ids, a deterministic reason_code, and concise server-generated reason. Examples include not_relevant, review_required, blocked, evidence_insufficient, and summary_failed. These sources remain outside report evidence.

## New report attempts

Create agentic_research_report_attempts with scope, attempt_number (1 or 2), status (started, pass, fail, or unusable), input fingerprint, model, prompt, contract version, untrusted raw response, structured validation errors, and timestamps.

Attempt transitions are started to pass, started to fail, or started to unusable. A non-passing first attempt permits one second attempt. A safe draft must have a valid schema, at least one known topic-scoped source reference for every factual finding, and no findings in insufficient sections. A pass requires all three equal-weight quality checks: planned-topic coverage, qualified-source representation, and applicable narrative length. If neither attempt passes, the report store selects the safe draft with the greatest number of passed checks; a tie selects the second attempt. If neither is safe, it saves a platform fallback evidence briefing with a model_unavailable, malformed_model_response, or unsafe_model_draft reason. The research workflow completes after the package is stored; it fails only when the platform cannot read the report inputs or write the package.

## Read model

Extend the existing ResearchReport API DTO with report ID, contract version, quality grade, quality reasons, report origin, currentness, supporting-source mapping, and exclusions. The latest report is current only when its frozen input fingerprint matches the applicable current input bundle. Attempt diagnostics never appear as the report itself.
