"""Deterministic contract coverage for grounded final-report decisions."""

import asyncio
import json
from types import SimpleNamespace
from uuid import uuid4

from app.agentic_research.contracts import (
    FinalReportDraft,
    ReportInput,
    TopicCoverage,
    TopicCoverageEvidence,
)
from app.agentic_research.reporting import ResearchReportingService, _assess_draft, _render_fallback


def _inputs() -> list[ReportInput]:
    return [
        ReportInput(
            topic_record_id=uuid4(),
            topic_id="agent-identity",
            topic="Agent identity and trust",
            summary_artifact_id=uuid4(),
            source_ref="source-01",
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
            source_ref="source-02",
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


def test_report_draft_requires_known_topic_scoped_source_references() -> None:
    inputs = _inputs()
    draft = FinalReportDraft.model_validate({
        "sections": [{
            "topic_id": "agent-identity",
            "evidence_status": "supported",
            "findings": [{"text": "Identity matters.", "source_refs": ["unknown"]}],
            "source_refs": [],
        }]
    })

    assessment = _assess_draft(draft, _coverage(inputs), inputs)

    assert assessment.safe is False
    assert assessment.errors == ["Unknown source_ref unknown."]


def test_safe_incomplete_draft_receives_fail_quality_reason() -> None:
    inputs = _inputs()
    draft = FinalReportDraft.model_validate({
        "sections": [{
            "topic_id": "agent-identity",
            "evidence_status": "supported",
            "findings": [{"text": "Identity matters.", "source_refs": ["source-01"]}],
            "source_refs": [],
        }]
    })

    assessment = _assess_draft(draft, _coverage(inputs), inputs)

    assert assessment.safe is True
    assert assessment.passed is False
    assert [reason.code for reason in assessment.reasons] == [
        "unrepresented_qualified_source"
    ]


def test_fallback_briefing_only_links_to_stored_summary_references() -> None:
    inputs = _inputs()

    markdown = _render_fallback(_coverage(inputs), inputs)

    assert "#summary:source-01" in markdown
    assert "https://example.test/identity" not in markdown


class _FakeStore:
    def __init__(self, inputs: list[ReportInput], coverage: list[TopicCoverage]) -> None:
        self.inputs = inputs
        self.coverage = coverage
        self.saved: dict[str, object] | None = None

    async def report_inputs(self, *_: object) -> list[ReportInput]:
        return self.inputs

    async def list_topic_coverage(self, *_: object) -> list[TopicCoverage]:
        return self.coverage

    async def report_exclusions(self, *_: object) -> list[object]:
        return []

    async def save_report_package(self, *args: object) -> SimpleNamespace:
        self.saved = {"grade": args[7], "origin": args[9], "attempts": args[-1]}
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


def test_service_corrects_one_incomplete_draft_and_stores_pass() -> None:
    inputs = _inputs()
    first = json.dumps({"sections": [{
        "topic_id": "agent-identity", "evidence_status": "supported",
        "findings": [{"text": "Identity matters.", "source_refs": ["source-01"]}],
        "source_refs": [],
    }]})
    second = json.dumps({"sections": [{
        "topic_id": "agent-identity", "evidence_status": "supported",
        "findings": [{
            "text": "Identity and provenance matter.",
            "source_refs": ["source-01", "source-02"],
        }],
        "source_refs": ["source-01", "source-02"],
    }]})
    store = _FakeStore(inputs, _coverage(inputs))
    client = _Client([first, second])
    service = ResearchReportingService(store, _Provider(), lambda _: client)

    report = asyncio.run(service.final_report(uuid4(), uuid4(), "How do agents identify sources?"))

    assert report.quality_grade == "PASS"
    assert store.saved["grade"] == "PASS"
    assert store.saved["origin"] == "model_pass"
    assert len(store.saved["attempts"]) == 2
    assert "Correct these issues" in client.calls[1]["messages"][0]["content"]


def test_service_stores_fallback_after_two_malformed_model_responses() -> None:
    inputs = _inputs()
    store = _FakeStore(inputs, _coverage(inputs))
    client = _Client(["not json", "also not json"])
    service = ResearchReportingService(store, _Provider(), lambda _: client)

    report = asyncio.run(service.final_report(uuid4(), uuid4(), "How do agents identify sources?"))

    assert report.quality_grade == "FAIL"
    assert store.saved["origin"] == "fallback"
    assert len(store.saved["attempts"]) == 2
