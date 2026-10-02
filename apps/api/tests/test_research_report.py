"""Read-only API coverage for stored grounded research reports."""

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import httpx

from app.agentic_research.contracts import ReportQualityReason, ResearchReport
from app.main import create_app
from tests.test_web_research import authenticated_app


def test_report_read_returns_only_the_current_workspace_report() -> None:
    run_id = uuid4()
    app, user = authenticated_app(create_app())

    class FakeAgenticStore:
        async def get_report(self, workspace_id, requested_run_id):
            assert workspace_id == user.workspace_id
            assert requested_run_id == run_id
            return ResearchReport(
                run_id=run_id,
                markdown="# Grounded report",
                model_name="qwen3:1.7b",
                prompt_version="agentic-research-final-report-v2",
                contract_version="grounded-final-report-v1",
                quality_grade="PASS",
                report_origin="model_pass",
                created_at=datetime.now(UTC),
            )

    app.state.agentic_research_store = FakeAgenticStore()

    async def request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.get(f"/v1/research/runs/{run_id}/report")

    response = asyncio.run(request())

    assert response.status_code == 200
    assert response.json()["markdown"] == "# Grounded report"
    assert response.json()["quality_grade"] == "PASS"
    assert response.json()["report_origin"] == "model_pass"


def test_report_read_returns_not_found_when_no_report_exists() -> None:
    run_id = uuid4()
    app, _ = authenticated_app(create_app())

    class FakeAgenticStore:
        async def get_report(self, *_):
            return None

    app.state.agentic_research_store = FakeAgenticStore()

    async def request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.get(f"/v1/research/runs/{run_id}/report")

    response = asyncio.run(request())

    assert response.status_code == 404


def test_report_read_exposes_fail_grade_quality_reasons() -> None:
    run_id = uuid4()
    app, user = authenticated_app(create_app())

    class FakeAgenticStore:
        async def get_report(self, workspace_id, requested_run_id):
            assert workspace_id == user.workspace_id
            assert requested_run_id == run_id
            return ResearchReport(
                run_id=run_id,
                markdown="# Evidence briefing",
                model_name="qwen3:1.7b",
                prompt_version="agentic-research-final-report-v2",
                contract_version="grounded-final-report-v1",
                quality_grade="FAIL",
                quality_reasons=[
                    ReportQualityReason(
                        code="unsupported_citation_label",
                        message=(
                            "Agent identity and trust: the model cited a source label "
                            "that was not supplied for this topic."
                        ),
                    )
                ],
                report_origin="model_fail",
                created_at=datetime.now(UTC),
            )

    app.state.agentic_research_store = FakeAgenticStore()

    async def request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.get(f"/v1/research/runs/{run_id}/report")

    response = asyncio.run(request())

    assert response.status_code == 200
    assert response.json()["quality_grade"] == "FAIL"
    assert response.json()["quality_reasons"] == [
        {
            "code": "unsupported_citation_label",
            "message": (
                "Agent identity and trust: the model cited a source label "
                "that was not supplied for this topic."
            ),
        }
    ]


def test_report_read_preserves_historical_currentness_flag() -> None:
    run_id = uuid4()
    app, _ = authenticated_app(create_app())

    class FakeAgenticStore:
        async def get_report(self, *_):
            return ResearchReport(
                run_id=run_id,
                markdown="# Historical report",
                model_name="qwen3:1.7b",
                prompt_version="agentic-research-final-report-v2",
                contract_version="grounded-final-report-v1",
                quality_grade="PASS",
                report_origin="model_pass",
                current=False,
                created_at=datetime.now(UTC),
            )

    app.state.agentic_research_store = FakeAgenticStore()

    async def request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.get(f"/v1/research/runs/{run_id}/report")

    response = asyncio.run(request())

    assert response.status_code == 200
    assert response.json()["current"] is False
    assert response.json()["markdown"] == "# Historical report"
