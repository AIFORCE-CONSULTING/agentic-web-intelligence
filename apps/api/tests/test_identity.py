"""Security-focused tests for the local-first identity service."""

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.identity.contracts import AuthenticatedUser
from app.identity.service import AuthenticationError, IdentityService


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

        async def create_session(self, _: object, token: str) -> None:
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
