"""Contract coverage for bounded, recoverable local summary responses."""

import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError
from app.evidence_summaries.service import ChunkSummary, EvidenceSummaryService, FinalSummary


def test_chunk_summary_accepts_normalized_keyword_phrases() -> None:
    summary = "The local platform stores a research record for every accepted source."

    result = ChunkSummary(
        summary=summary,
        keywords=["local platform", "research record", "accepted source"],
    )

    assert result.keywords == ["local platform", "research record", "accepted source"]


def test_chunk_summary_rejects_duplicate_keywords_after_normalization() -> None:
    with pytest.raises(ValidationError, match="duplicate_or_empty_keyword"):
        ChunkSummary(
            summary="The platform records evidence and keeps evidence available for review.",
            keywords=["platform", "evidence", " Evidence "],
        )


def test_final_summary_allows_seven_keywords_and_requires_sufficiency_flag() -> None:
    result = FinalSummary(
        summary=(
            "The platform records evidence, trust policy, model response, and report findings. "
            "It also preserves source context and research status for operators."
        ),
        keywords=[
            "platform", "evidence", "trust policy", "model response", "report findings",
            "source context", "research status",
        ],
        evidence_sufficient=True,
    )

    assert result.evidence_sufficient is True


def test_invalid_completed_response_gets_one_safe_corrective_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, object]] = []

    class Store:
        async def reserve_model_attempt(self, *_):
            return "reserved"

        async def reject_model_attempt(self, *args):
            assert args[-1] == "invalid_json"

        async def accept_model_attempt(self, *_):
            return None

        async def mark_model_attempt_dependency_failed(self, *_):
            raise AssertionError("The provider completed both responses.")

    class Provider:
        async def configuration(self, _):
            return SimpleNamespace(
                model_name="qwen3:1.7b", endpoint_url="http://host.docker.internal:11434"
            )

    responses = iter(
        [
            "not-json",
            '{"summary":"The platform stores evidence for research.","keywords":["platform","evidence","research"]}',
        ]
    )

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"message": {"content": next(responses)}}

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

        async def post(self, _, json):
            calls.append(json)
            return Response()

    monkeypatch.setattr("app.evidence_summaries.service.httpx.AsyncClient", lambda **_: Client())
    execution = SimpleNamespace(id=uuid4(), workspace_id=uuid4(), regeneration_attempt=0)
    service = EvidenceSummaryService(Store(), object(), Provider())

    result = asyncio.run(
        service._call_model(
            execution,
            "https://example.com/source",
            "content-hash",
            "chunk",
            "0",
            "Fixed instruction.",
            "Trusted evidence stays identical.",
            ChunkSummary,
        )
    )

    assert result.keywords == ["platform", "evidence", "research"]
    assert len(calls) == 2
    assert calls[0]["messages"][1]["content"] == calls[1]["messages"][1]["content"]
    assert "invalid_json" in calls[1]["messages"][0]["content"]
