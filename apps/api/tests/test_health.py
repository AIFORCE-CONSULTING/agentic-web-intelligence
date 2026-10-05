import asyncio

import httpx

from app.database_bootstrap import DatabaseBootstrapReadiness
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


def test_readiness_reports_database_bootstrap_not_ready() -> None:
    app = create_app()
    app.state.database_bootstrap_readiness = lambda: asyncio.sleep(
        0,
        result=DatabaseBootstrapReadiness(
            status="not_run",
            detail="Database bootstrap has not run.",
        ),
    )

    async def get_readiness() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.get("/health/ready")

    response = asyncio.run(get_readiness())

    assert response.status_code == 503
    assert response.json()["status"] == "not_run"


def test_readiness_reports_ready_after_database_bootstrap() -> None:
    app = create_app()
    app.state.database_bootstrap_readiness = lambda: asyncio.sleep(
        0,
        result=DatabaseBootstrapReadiness(
            status="ready",
            detail="Database bootstrap completed and runtime work may proceed.",
        ),
    )

    async def get_readiness() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.get("/health/ready")

    response = asyncio.run(get_readiness())

    assert response.status_code == 200
    assert response.json()["status"] == "ready"
