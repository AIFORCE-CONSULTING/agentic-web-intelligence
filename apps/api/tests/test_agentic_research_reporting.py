"""Deterministic contract coverage for grounded final-report decisions."""

import asyncio
import json
from types import SimpleNamespace
from uuid import uuid4

import httpx

from app.agentic_research.contracts import (
    ReportExclusion,
    ReportInput,
    TopicCoverage,
    TopicCoverageEvidence,
    TopicFindingDraft,
)
from app.agentic_research.reporting import (
    ResearchReportingService,
    _assess_topic_draft,
    _render_fallback,
    assign_report_source_ref,
    normalize_citation_label,
)


def _inputs() -> list[ReportInput]:
    return [
        ReportInput(
            topic_record_id=uuid4(),
            topic_id="agent-identity",
            topic="Agent identity and trust",
            summary_artifact_id=uuid4(),
            source_ref="S01",
            source_url="https://example.test/identity",
            source_title="Identity standard",
            summary_text="A signed identity can help a service distinguish an agent.",
            content_hash="hash-1",
            position=1,
        ),
        ReportInput(
            topic_record_id=uuid4(),
            topic_id="agent-identity",
            topic="Agent identity and trust",
            summary_artifact_id=uuid4(),
            source_ref="S02",
            source_url="https://example.test/provenance",
            source_title="Provenance guidance",
            summary_text="Provenance records help explain where evidence came from.",
            content_hash="hash-2",
            position=2,
        ),
    ]


def _coverage(inputs: list[ReportInput]) -> list[TopicCoverage]:
    return [
        TopicCoverage(
            topic_id="agent-identity",
            topic="Agent identity and trust",
            search_query="agent identity",
            status="covered",
            evidence=[
                TopicCoverageEvidence(
                    source_url=item.source_url,
                    content_hash=item.content_hash,
                    evidence_id=uuid4(),
                    trust_evaluation_id=uuid4(),
                    relevance_decision_id=uuid4(),
                    summary_artifact_id=item.summary_artifact_id,
                    qualified_at="2026-10-01T00:00:00Z",
                )
                for item in inputs
            ],
        )
    ]


def _multi_topic_inputs() -> list[ReportInput]:
    topics = [
        ("agent-identity", "Agent identity and trust", "identity"),
        ("agent-commerce", "Agentic commerce readiness", "commerce"),
        ("agent-ux", "Agentic user experience", "ux"),
    ]
    inputs: list[ReportInput] = []
    for position, (topic_id, topic, slug) in enumerate(topics, start=1):
        inputs.append(
            ReportInput(
                topic_record_id=uuid4(),
                topic_id=topic_id,
                topic=topic,
                summary_artifact_id=uuid4(),
                source_ref=assign_report_source_ref(position),
                source_url=f"https://example.test/{slug}",
                source_title=f"{topic} source",
                summary_text=f"Stored summary for {topic.lower()}.",
                content_hash=f"hash-{slug}",
                position=position,
            )
        )
    return inputs


def _many_topic_inputs() -> list[ReportInput]:
    topics = [
        ("agent-identity", "Agent identity and trust", "identity", 4),
        ("agent-commerce", "Agentic commerce readiness", "commerce", 3),
        ("agent-ux", "Agentic user experience", "ux", 3),
    ]
    inputs: list[ReportInput] = []
    position = 1
    for topic_id, topic, slug, count in topics:
        for index in range(1, count + 1):
            inputs.append(
                ReportInput(
                    topic_record_id=uuid4(),
                    topic_id=topic_id,
                    topic=topic,
                    summary_artifact_id=uuid4(),
                    source_ref=assign_report_source_ref(position),
                    source_url=f"https://example.test/{slug}-{index}",
                    source_title=f"{topic} source {index}",
                    summary_text=f"Stored summary {index} for {topic.lower()}.",
                    content_hash=f"hash-{slug}-{index}",
                    position=position,
                )
            )
            position += 1
    return inputs


def _coverage_from_inputs(inputs: list[ReportInput]) -> list[TopicCoverage]:
    topics: dict[str, ReportInput] = {}
    for item in inputs:
        topics.setdefault(item.topic_id, item)
    return [
        TopicCoverage(
            topic_id=item.topic_id,
            topic=item.topic,
            search_query=item.topic,
            status="covered",
            evidence=[],
        )
        for item in topics.values()
    ]


def test_multi_topic_fixture_has_stable_planned_topics_and_report_labels() -> None:
    inputs = _multi_topic_inputs()

    assert [item.topic_id for item in inputs] == [
        "agent-identity",
        "agent-commerce",
        "agent-ux",
    ]
    assert [item.source_ref for item in inputs] == ["S01", "S02", "S03"]


def test_report_draft_requires_known_topic_scoped_source_references() -> None:
    inputs = _inputs()
    draft = TopicFindingDraft.model_validate({
        "findings": [{"text": "Identity matters.", "source_refs": ["unknown"]}]
    })

    assessment = _assess_topic_draft(draft, _coverage(inputs)[0], inputs)

    assert assessment.safe is False
    assert assessment.errors == ["Unknown source_ref unknown."]


def test_report_source_refs_are_simple_one_based_labels() -> None:
    assert [assign_report_source_ref(index) for index in range(1, 4)] == [
        "S01",
        "S02",
        "S03",
    ]


def test_harmless_citation_label_variants_are_normalized() -> None:
    allowed = {"S01", "S02", "S10"}

    assert normalize_citation_label("s01", allowed) == "S01"
    assert normalize_citation_label("S 02", allowed) == "S02"
    assert normalize_citation_label("S1", allowed) == "S01"
    assert normalize_citation_label("S10", allowed) == "S10"
    assert normalize_citation_label("S03", allowed) is None
    assert normalize_citation_label("source-01", allowed) is None


def test_normalized_citation_labels_count_toward_source_coverage() -> None:
    inputs = _inputs()
    draft = TopicFindingDraft.model_validate({
        "findings": [{
            "text": "Identity and provenance matter.",
            "source_refs": ["s01", "S 02"],
        }]
    })

    assessment = _assess_topic_draft(draft, _coverage(inputs)[0], inputs)

    assert assessment.safe is True
    assert assessment.passed is True
    assert {item[2] for item in assessment.contributions} == {"S01", "S02"}


def test_topic_finding_draft_rejects_empty_findings() -> None:
    inputs = _inputs()
    draft = TopicFindingDraft.model_validate({"findings": []})

    assessment = _assess_topic_draft(draft, _coverage(inputs)[0], inputs)

    assert assessment.safe is False
    assert assessment.errors == ["Topic agent-identity did not include any findings."]


def test_fallback_briefing_only_links_to_stored_summary_references() -> None:
    inputs = _inputs()

    markdown = _render_fallback(_coverage(inputs), inputs)

    assert "#summary:S01" in markdown
    assert "https://example.test/identity" not in markdown


class _FakeStore:
    def __init__(
        self,
        inputs: list[ReportInput],
        coverage: list[TopicCoverage],
        exclusions: list[ReportExclusion] | None = None,
    ) -> None:
        self.inputs = inputs
        self.coverage = coverage
        self.exclusions = exclusions or []
        self.report_exclusion_calls = 0
        self.saved: dict[str, object] | None = None

    async def report_inputs(self, *_: object) -> list[ReportInput]:
        return self.inputs

    async def list_topic_coverage(self, *_: object) -> list[TopicCoverage]:
        return self.coverage

    async def report_exclusions(self, *_: object) -> list[object]:
        self.report_exclusion_calls += 1
        return self.exclusions

    async def save_report_package(self, *args: object) -> SimpleNamespace:
        self.saved = {
            "markdown": args[2],
            "grade": args[7],
            "origin": args[9],
            "inputs": args[10],
            "exclusions": args[12],
            "quality_reasons": args[8],
            "attempts": args[-1],
        }
        return SimpleNamespace(markdown=args[2], quality_grade=args[7])


class _Provider:
    async def configuration(self, _: object) -> SimpleNamespace:
        return SimpleNamespace(endpoint_url="http://ollama.test", model_name="test-model")


class _Client:
    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.calls: list[dict[str, object]] = []

    async def chat(self, **kwargs: object) -> SimpleNamespace:
        self.calls.append(kwargs)
        return SimpleNamespace(message=SimpleNamespace(content=self.responses.pop(0)))


class _FailingClient:
    async def chat(self, **_: object) -> SimpleNamespace:
        raise httpx.ReadTimeout("timed out")


def test_service_corrects_one_malformed_topic_draft_and_stores_pass() -> None:
    inputs = _inputs()
    first = json.dumps({
        "topic_id": "legacy-unexpected",
        "findings": [{
            "text": "Identity and provenance matter.",
            "source_refs": ["S01", "S02"],
        }],
    })
    second = json.dumps({
        "findings": [{
            "text": "Identity and provenance matter.",
            "source_refs": ["S01", "S02"],
        }]
    })
    store = _FakeStore(inputs, _coverage(inputs))
    client = _Client([first, second])
    service = ResearchReportingService(store, _Provider(), lambda _: client)

    report = asyncio.run(service.final_report(uuid4(), uuid4(), "How do agents identify sources?"))

    assert report.quality_grade == "PASS"
    assert store.saved["grade"] == "PASS"
    assert store.saved["origin"] == "model_pass"
    assert len(store.saved["attempts"]) == 2
    assert store.saved["attempts"][0].topic_id == "agent-identity"
    assert "Correct these issues" in client.calls[1]["messages"][0]["content"]


def test_service_sends_only_one_topic_sources_to_each_model_call() -> None:
    inputs = _multi_topic_inputs()
    coverage = [
        TopicCoverage(
            topic_id=item.topic_id,
            topic=item.topic,
            search_query=item.topic,
            status="covered",
            evidence=[],
        )
        for item in inputs
    ]
    responses = [
        json.dumps({
            "findings": [{
                "text": f"Finding {item.source_ref}",
                "source_refs": [item.source_ref],
            }]
        })
        for item in inputs
    ]
    store = _FakeStore(inputs, coverage)
    client = _Client(responses)
    service = ResearchReportingService(store, _Provider(), lambda _: client)

    report = asyncio.run(service.final_report(uuid4(), uuid4(), "How should agents work?"))

    assert report.quality_grade == "PASS"
    assert len(client.calls) == 3
    payloads = [json.loads(call["messages"][1]["content"]) for call in client.calls]
    assert [payload["topic"]["topic_id"] for payload in payloads] == [
        "agent-identity",
        "agent-commerce",
        "agent-ux",
    ]
    source_refs_by_payload = [
        [source["source_ref"] for source in payload["qualified_sources"]]
        for payload in payloads
    ]
    assert source_refs_by_payload == [
        ["S01"],
        ["S02"],
        ["S03"],
    ]


def test_service_stores_fallback_after_two_malformed_model_responses() -> None:
    inputs = _inputs()
    store = _FakeStore(inputs, _coverage(inputs))
    client = _Client(["not json", "also not json"])
    service = ResearchReportingService(store, _Provider(), lambda _: client)

    report = asyncio.run(service.final_report(uuid4(), uuid4(), "How do agents identify sources?"))

    assert report.quality_grade == "FAIL"
    assert store.saved["origin"] == "fallback"
    assert len(store.saved["attempts"]) == 2
    assert {attempt.topic_id for attempt in store.saved["attempts"]} == {"agent-identity"}
    assert store.saved["quality_reasons"][0].code == "malformed_topic_output"


def test_service_records_timing_when_model_times_out() -> None:
    inputs = _inputs()
    store = _FakeStore(inputs, _coverage(inputs))
    service = ResearchReportingService(store, _Provider(), lambda _: _FailingClient())

    report = asyncio.run(service.final_report(uuid4(), uuid4(), "How do agents identify sources?"))

    assert report.quality_grade == "FAIL"
    assert store.saved["origin"] == "fallback"
    attempts = store.saved["attempts"]
    assert len(attempts) == 1
    assert attempts[0].failure_code == "model_timeout"
    assert store.saved["quality_reasons"][0].code == "model_timeout"
    assert attempts[0].input_characters > 0
    assert attempts[0].duration_ms is not None


def test_service_explains_unsupported_topic_citation_label() -> None:
    inputs = _inputs()
    response = json.dumps({
        "findings": [{
            "text": "Identity matters.",
            "source_refs": ["S99"],
        }]
    })
    store = _FakeStore(inputs, _coverage(inputs))
    client = _Client([response, response])
    service = ResearchReportingService(store, _Provider(), lambda _: client)

    report = asyncio.run(service.final_report(uuid4(), uuid4(), "How do agents identify sources?"))

    assert report.quality_grade == "FAIL"
    assert store.saved["quality_reasons"][0].code == "unsupported_citation_label"
    assert store.saved["attempts"][0].failure_code == "unsupported_citation_label"


def test_report_renders_stored_citation_links_and_all_topic_sources() -> None:
    inputs = _inputs()
    response = json.dumps({
        "findings": [{
            "text": "Identity can be verified through signed metadata.",
            "source_refs": ["s01"],
        }]
    })
    store = _FakeStore(inputs, _coverage(inputs))
    client = _Client([response])
    service = ResearchReportingService(store, _Provider(), lambda _: client)

    report = asyncio.run(service.final_report(uuid4(), uuid4(), "How do agents identify sources?"))

    assert report.quality_grade == "PASS"
    assert "[S01](#summary:S01)" in report.markdown
    assert "#summary:s01" not in report.markdown
    assert "Sources for this topic:" in report.markdown
    assert "[Identity standard](#summary:S01)" in report.markdown
    assert "[Provenance guidance](#summary:S02)" in report.markdown


def test_ten_plus_qualified_summaries_still_render_topic_organized_report() -> None:
    inputs = _many_topic_inputs()
    coverage = _coverage_from_inputs(inputs)
    responses = []
    for topic in coverage:
        refs = [item.source_ref for item in inputs if item.topic_id == topic.topic_id]
        responses.append(
            json.dumps({
                "findings": [{
                    "text": f"{topic.topic} has multiple grounded source summaries.",
                    "source_refs": refs[:2],
                }]
            })
        )
    store = _FakeStore(inputs, coverage)
    client = _Client(responses)
    service = ResearchReportingService(store, _Provider(), lambda _: client)

    report = asyncio.run(service.final_report(uuid4(), uuid4(), "How should agents work?"))

    assert len(inputs) == 10
    assert report.quality_grade == "PASS"
    assert report.markdown.count("## ") == 3
    assert "## Agent identity and trust" in report.markdown
    assert "## Agentic commerce readiness" in report.markdown
    assert "## Agentic user experience" in report.markdown
    assert "[Agentic user experience source 3](#summary:S10)" in report.markdown


def test_exclusion_label_changes_do_not_change_supporting_report_inputs() -> None:
    inputs = _inputs()
    exclusions = [
        ReportExclusion(
            title="Publisher denied source",
            url="https://example.test/denied",
            topic_ids=["agent-identity"],
            reason_code="access_denied_by_publisher",
            reason="The publisher or website rejected automated access.",
        )
    ]
    response = json.dumps({
        "findings": [{
            "text": "Identity can be verified through signed metadata.",
            "source_refs": ["S01"],
        }]
    })
    store = _FakeStore(inputs, _coverage(inputs), exclusions)
    client = _Client([response])
    service = ResearchReportingService(store, _Provider(), lambda _: client)

    report = asyncio.run(service.final_report(uuid4(), uuid4(), "How do agents identify sources?"))

    assert report.quality_grade == "PASS"
    assert store.saved["inputs"] == inputs
    assert store.saved["exclusions"] == exclusions


def test_service_uses_store_owned_exclusion_reasons_without_model_authorship() -> None:
    inputs = _inputs()
    exclusions = [
        ReportExclusion(
            title="Unreachable source",
            url="https://example.test/unreachable",
            topic_ids=["agent-identity"],
            reason_code="unreachable",
            reason="No usable evidence was captured for report findings.",
        )
    ]
    response = json.dumps({
        "findings": [{
            "text": "Identity can be verified through signed metadata.",
            "source_refs": ["S01"],
        }]
    })
    store = _FakeStore(inputs, _coverage(inputs), exclusions)
    client = _Client([response])
    service = ResearchReportingService(store, _Provider(), lambda _: client)

    asyncio.run(service.final_report(uuid4(), uuid4(), "How do agents identify sources?"))

    assert store.report_exclusion_calls == 1
    assert store.saved["exclusions"] == exclusions
    model_payload = json.loads(client.calls[0]["messages"][1]["content"])
    assert "exclusions" not in model_payload
    assert "No usable evidence was captured" not in client.calls[0]["messages"][1]["content"]
