"""Tests for the narrow server-only GitHub Projects connector."""

import asyncio
import json
from datetime import UTC, datetime
from uuid import uuid4

import httpx

from app.github_projects.contracts import GitHubDraftItem
from app.github_projects.service import GitHubProjectsBoundary, GitHubProjectsService
from app.identity.contracts import AuthenticatedServiceIdentity, AuthenticatedUser
from app.settings import Settings


def test_github_projects_boundary_requires_one_project_and_server_secret() -> None:
    disabled = GitHubProjectsBoundary(Settings()).status()
    assert disabled.mode == "disabled"

    incomplete = GitHubProjectsBoundary(
        Settings(github_project_owner="AIFORCE-CONSULTING")
    ).status()
    assert incomplete.mode == "invalid"
    assert "GITHUB_PROJECT_NUMBER" in incomplete.detail
    assert "GITHUB_CONNECTOR_TOKEN" in incomplete.detail

    ready = GitHubProjectsBoundary(
        Settings(
            github_project_owner="AIFORCE-CONSULTING",
            github_project_number=12,
            github_connector_token="not-exposed",
        )
    ).status()
    assert ready.mode == "ready"
    assert ready.project_url == "https://github.com/orgs/AIFORCE-CONSULTING/projects/12"
    assert "not-exposed" not in ready.model_dump_json()


def test_github_projects_creates_draft_then_sets_existing_priority() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.headers["Authorization"] == "Bearer connector-secret"
        if request.url.path.endswith("/fields"):
            return httpx.Response(
                200,
                json=[
                    {
                        "name": "Priority",
                        "data_type": "single_select",
                        "node_id": "PVTF_priority",
                        "options": [{"id": "high", "name": {"raw": "High"}}],
                    }
                ],
        )
        if request.url.path.endswith("/drafts"):
            assert json.loads(request.content) == {
                "title": "Document connector",
                "body": "Operator work",
            }
            return httpx.Response(
                201,
                json={
                    "value": {
                        "node_id": "PVTI_draft",
                        "content": {"title": "Document connector"},
                    }
                },
            )
        if request.url.path.endswith("/projectsV2/12"):
            return httpx.Response(200, json={"title": "Roadmap", "node_id": "PVT_project"})
        if request.url.path == "/graphql":
            payload = json.loads(request.content)
            assert payload["variables"] == {
                "projectId": "PVT_project",
                "itemId": "PVTI_draft",
                "fieldId": "PVTF_priority",
                "optionId": "high",
            }
            return httpx.Response(
                200,
                json={"data": {"updateProjectV2ItemFieldValue": {"projectV2Item": {"id": "x"}}}},
            )
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    service = GitHubProjectsService(
        GitHubProjectsBoundary(
            Settings(
                github_project_owner="AIFORCE-CONSULTING",
                github_project_number=12,
                github_connector_token="connector-secret",
            )
        ),
        transport=httpx.MockTransport(handler),
    )

    created = asyncio.run(
        service.create_draft_item("Document connector", "Operator work", "High")
    )

    assert created == GitHubDraftItem(
        id="PVTI_draft", title="Document connector", priority="High"
    )
    assert [request.method for request in requests] == ["GET", "POST", "GET", "POST"]


def test_github_projects_lists_an_empty_draft_roadmap() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/projectsV2/12"):
            return httpx.Response(200, json={"node_id": "PVT_project"})
        if request.url.path == "/graphql":
            payload = json.loads(request.content)
            assert payload["variables"] == {"projectId": "PVT_project"}
            return httpx.Response(200, json={"data": {"node": {"items": {"nodes": []}}}})
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    service = GitHubProjectsService(
        GitHubProjectsBoundary(
            Settings(
                github_project_owner="AIFORCE-CONSULTING",
                github_project_number=12,
                github_connector_token="connector-secret",
            )
        ),
        transport=httpx.MockTransport(handler),
    )

    assert asyncio.run(service.list_draft_items()).items == []


def test_github_projects_uses_submitted_title_when_github_omits_content() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/drafts")
        return httpx.Response(201, json={"value": {"node_id": "PVTI_draft"}})

    service = GitHubProjectsService(
        GitHubProjectsBoundary(
            Settings(
                github_project_owner="AIFORCE-CONSULTING",
                github_project_number=12,
                github_connector_token="connector-secret",
            )
        ),
        transport=httpx.MockTransport(handler),
    )

    created = asyncio.run(service.create_draft_item("Dark mode", None, None))

    assert created == GitHubDraftItem(id="PVTI_draft", title="Dark mode", priority=None)


def test_github_projects_rejects_service_identities_and_viewers(
    monkeypatch,
) -> None:
    from app.main import create_app

    workspace_id = uuid4()
    viewer = AuthenticatedUser(
        id=uuid4(),
        email="viewer@example.com",
        workspace_id=workspace_id,
        workspace_name="Workspace A",
        role="viewer",
        authenticated_at=datetime.now(UTC),
    )
    service_identity = AuthenticatedServiceIdentity(
        id=uuid4(),
        name="research-worker",
        workspace_id=workspace_id,
        workspace_name="Workspace A",
        permissions=frozenset({"research.read"}),
        authenticated_at=datetime.now(UTC),
    )

    class FakeIdentityService:
        async def current_user(self, token: str | None):
            return viewer if token == "viewer" else None

        async def current_service_identity(self, authorization: str | None):
            return service_identity if authorization else None

    monkeypatch.setattr("app.main.get_settings", lambda: Settings())
    app = create_app()
    app.state.identity_service = FakeIdentityService()

    async def request() -> tuple[httpx.Response, httpx.Response]:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            client.cookies.set("platform_session", "viewer")
            denied_viewer = await client.get("/v1/github/projects/status")
            client.cookies.clear()
            denied_service = await client.get(
                "/v1/github/projects/status", headers={"Authorization": "Bearer awi_si_test"}
            )
            return denied_viewer, denied_service

    denied_viewer, denied_service = asyncio.run(request())
    assert denied_viewer.status_code == 403
    assert denied_service.status_code == 403
