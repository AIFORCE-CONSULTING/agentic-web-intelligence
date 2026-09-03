"""Security-focused tests for the local-first identity service."""

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest

from app.identity.contracts import AuthenticatedUser
from app.identity.service import AuthenticationError, IdentityService
from app.main import create_app
from app.settings import Settings


def test_bootstrap_requires_the_deployment_secret_and_creates_a_session() -> None:
    user = AuthenticatedUser(
        id=uuid4(),
        email="admin@example.com",
        workspace_id=uuid4(),
        workspace_name="Default workspace",
        role="administrator",
        authenticated_at=datetime.now(UTC),
    )

    class FakeStore:
        def __init__(self) -> None:
            self.sessions: list[str] = []

        async def create_bootstrap_admin(self, _: str, __: str) -> AuthenticatedUser:
            return user

        async def create_session(self, _: object, __: object, token: str) -> None:
            self.sessions.append(token)

    store = FakeStore()
    service = IdentityService(store, "a" * 32)
    with pytest.raises(AuthenticationError):
        asyncio.run(
            service.bootstrap_admin("wrong" * 8, user.email, "correct horse battery staple")
        )

    created, token = asyncio.run(
        service.bootstrap_admin("a" * 32, user.email, "correct horse battery staple")
    )
    assert created.role == "administrator"
    assert token in store.sessions


def test_sign_in_does_not_distinguish_missing_from_invalid_credentials() -> None:
    class FakeStore:
        async def authenticate_local(self, _: str) -> None:
            return None

    service = IdentityService(FakeStore(), "a" * 32)
    with pytest.raises(AuthenticationError, match="Invalid email or password"):
        asyncio.run(service.sign_in("missing@example.com", "not-the-password"))


def test_durable_routes_require_a_session_and_enforce_workspace_roles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A caller cannot turn a viewer session into write or audit authority."""

    workspace_id = uuid4()
    viewer = AuthenticatedUser(
        id=uuid4(),
        email="viewer@example.com",
        workspace_id=workspace_id,
        workspace_name="Workspace A",
        role="viewer",
        authenticated_at=datetime.now(UTC),
    )

    class FakeIdentityService:
        async def current_user(self, token: str | None) -> AuthenticatedUser | None:
            return viewer if token == "viewer-session" else None

    class FakeResearchStore:
        def __init__(self) -> None:
            self.list_workspace_id = None

        async def list_runs(self, received_workspace_id, limit: int) -> list[object]:
            self.list_workspace_id = received_workspace_id
            assert limit == 25
            return []

    monkeypatch.setattr(
        "app.main.get_settings",
        lambda: Settings(database_url="postgresql://test", searxng_base_url=None),
    )
    app = create_app()
    store = FakeResearchStore()
    app.state.identity_service = FakeIdentityService()
    app.state.research_store = store

    async def request() -> tuple[httpx.Response, httpx.Response, httpx.Response]:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            anonymous = await client.get("/v1/research/runs")
            client.cookies.set("platform_session", "viewer-session")
            readable = await client.get("/v1/research/runs")
            denied = await client.post("/v1/research/search", json={"query": "evidence"})
            return anonymous, readable, denied

    anonymous, readable, denied = asyncio.run(request())

    assert anonymous.status_code == 401
    assert readable.status_code == 200
    assert store.list_workspace_id == workspace_id
    assert denied.status_code == 403
