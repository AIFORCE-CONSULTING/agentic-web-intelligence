import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest

from app.main import create_app
from app.web_research.contracts import (
    Evidence,
    ResearchRun,
    ResearchRunSummary,
    SearchResponse,
    SearchResult,
    ToolPolicyError,
    ToolProviderError,
)
from app.web_research.extractor import WebExtractor
from app.web_research.search import SearxngSearchProvider


def test_extractor_rejects_download_attachment() -> None:
    async def extract() -> None:
        transport = httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                headers={
                    "content-type": "application/zip",
                    "content-disposition": "attachment; filename=data.zip",
                },
                content=b"PK\x03\x04",
                request=request,
            )
        )
        async with httpx.AsyncClient(transport=transport) as client:
            await WebExtractor(client).extract("https://example.com/data.zip")

    with pytest.raises(ToolPolicyError, match="Attachments and file downloads"):
        asyncio.run(extract())


def test_extractor_returns_normalized_plain_text_evidence() -> None:
    async def extract():
        transport = httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                headers={"content-type": "text/plain; charset=utf-8"},
                content=b"A public evidence record.",
                request=request,
            )
        )
        async with httpx.AsyncClient(transport=transport) as client:
            return await WebExtractor(client).extract("https://example.com/evidence")

    evidence = asyncio.run(extract())

    assert evidence.text == "A public evidence record."
    assert evidence.content_type == "text/plain"
    assert evidence.extraction_method == "plain-text"


def test_extractor_returns_main_text_from_html() -> None:
    async def extract():
        transport = httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                headers={"content-type": "text/html; charset=utf-8"},
                content=b"<html><body><article><p>Public evidence.</p></article></body></html>",
                request=request,
            )
        )
        async with httpx.AsyncClient(transport=transport) as client:
            return await WebExtractor(client).extract("https://example.com/evidence")

    evidence = asyncio.run(extract())

    assert evidence.text == "Public evidence."
    assert evidence.extraction_method == "trafilatura"


def test_extractor_rejects_private_network_addresses() -> None:
    async def extract() -> None:
        async with httpx.AsyncClient() as client:
            await WebExtractor(client).extract("http://127.0.0.1/private")

    with pytest.raises(ToolPolicyError, match="Non-public network addresses"):
        asyncio.run(extract())


def test_extract_endpoint_returns_policy_errors_as_unprocessable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def reject(_: str) -> Evidence:
        raise ToolPolicyError("Attachments and file downloads are not permitted.")

    monkeypatch.setattr("app.main.run_extract_workflow", reject)

    async def request() -> httpx.Response:
        transport = httpx.ASGITransport(app=create_app())
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.post("/v1/research/extract", json={"url": "https://example.com/data.zip"})

    response = asyncio.run(request())

    assert response.status_code == 422
    assert response.json()["detail"] == "Attachments and file downloads are not permitted."


def test_searxng_provider_normalizes_and_bounds_results() -> None:
    async def search() -> SearchResponse:
        transport = httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "results": [
                        {"title": "Private", "url": "http://127.0.0.1/private"},
                        {
                            "title": "Public source",
                            "url": "https://example.com/evidence",
                            "content": "A source summary.",
                            "engine": "example-engine",
                        },
                        {"title": "Second source", "url": "https://example.org/second"},
                    ]
                },
                request=request,
            )
        )
        async with httpx.AsyncClient(transport=transport) as client:
            return await SearxngSearchProvider(client, "http://searxng:8080").search("evidence", 1)

    response = asyncio.run(search())

    assert response.query == "evidence"
    assert response.results == [
        SearchResult(
            title="Public source",
            url="https://example.com/evidence",
            snippet="A source summary.",
            engine="example-engine",
        )
    ]


def test_search_endpoint_returns_provider_unavailability(monkeypatch: pytest.MonkeyPatch) -> None:
    async def unavailable(_: str, __: int) -> SearchResponse:
        raise ToolProviderError("The search provider is unavailable.")

    monkeypatch.setattr("app.main.run_search_workflow", unavailable)

    async def request() -> httpx.Response:
        transport = httpx.ASGITransport(app=create_app())
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.post("/v1/research/search", json={"query": "evidence"})

    response = asyncio.run(request())

    assert response.status_code == 503
    assert response.json()["detail"] == "The search provider is unavailable."


def test_run_endpoint_persists_discovery_with_audit(monkeypatch: pytest.MonkeyPatch) -> None:
    run_id = uuid4()

    class FakeStore:
        def __init__(self) -> None:
            self.sources: list[SearchResult] = []

        async def create_run(self, question: str) -> ResearchRun:
            return ResearchRun(
                id=run_id,
                question=question,
                status="searching",
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )

        async def save_sources(self, _: object, sources: list[SearchResult]) -> None:
            self.sources = sources

        async def get_run(self, _: object) -> ResearchRun:
            return ResearchRun(
                id=run_id,
                question="evidence",
                status="ready",
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
                sources=self.sources,
            )

    async def search(_: str, __: int) -> SearchResponse:
        return SearchResponse(
            query="evidence",
            results=[SearchResult(title="Source", url="https://example.com", snippet="Summary")],
        )

    monkeypatch.setattr("app.main.run_search_workflow", search)
    app = create_app()
    app.state.research_store = FakeStore()

    async def request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.post("/v1/research/runs", json={"question": "evidence"})

    response = asyncio.run(request())

    assert response.status_code == 201
    assert response.json()["status"] == "ready"
    assert response.json()["sources"][0]["rank"] == 1


def test_run_library_lists_bounded_summaries() -> None:
    run_id = uuid4()

    class FakeStore:
        async def list_runs(self, limit: int) -> list[ResearchRunSummary]:
            assert limit == 25
            return [
                ResearchRunSummary(
                    id=run_id,
                    question="evidence",
                    status="ready",
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                    source_count=2,
                    evidence_count=1,
                )
            ]

    app = create_app()
    app.state.research_store = FakeStore()

    async def request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.get("/v1/research/runs")

    response = asyncio.run(request())

    assert response.status_code == 200
    assert response.json()["runs"][0]["evidence_count"] == 1
