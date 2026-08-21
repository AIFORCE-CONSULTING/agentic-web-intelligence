import asyncio

import httpx
import pytest

from app.web_research.contracts import ToolPolicyError
from app.web_research.extractor import WebExtractor


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


def test_extractor_rejects_private_network_addresses() -> None:
    async def extract() -> None:
        async with httpx.AsyncClient() as client:
            await WebExtractor(client).extract("http://127.0.0.1:8000/private")

    with pytest.raises(ToolPolicyError, match="Non-public network addresses"):
        asyncio.run(extract())
