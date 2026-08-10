import asyncio

import httpx

from app.main import create_app


def test_liveness_reports_platform_identity() -> None:
    async def get_liveness() -> httpx.Response:
        transport = httpx.ASGITransport(app=create_app())
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.get("/health/live")

    response = asyncio.run(get_liveness())

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "agentic-web-intelligence-api"
