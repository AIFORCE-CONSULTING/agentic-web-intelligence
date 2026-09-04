"""Security-focused tests for the local-first identity service."""

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest

from app.identity.audit import AuditDetailPolicyError, validate_audit_details
from app.identity.contracts import (
    AuthenticatedServiceIdentity,
    AuthenticatedUser,
    CreatedServiceIdentity,
    SecurityAuditEvent,
)
from app.identity.enterprise import EnterpriseIdentityBoundary
from app.identity.service import AuthenticationError, IdentityService
from app.main import create_app
from app.secrets import DeploymentSecrets, SecretName
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


def test_enterprise_identity_boundary_requires_complete_safe_configuration() -> None:
    disabled = EnterpriseIdentityBoundary(Settings()).status()
    assert disabled.mode == "disabled"
    assert disabled.issuer_url is None

    incomplete = EnterpriseIdentityBoundary(
        Settings(oidc_issuer_url="https://login.example.com/tenant")
    ).status()
    assert incomplete.mode == "invalid"
    assert "OIDC_CLIENT_ID" in incomplete.detail

    ready = EnterpriseIdentityBoundary(
        Settings(
            oidc_provider_name="Example Identity",
            oidc_issuer_url="https://login.example.com/tenant/",
            oidc_client_id="platform-client",
            oidc_client_secret="not-exposed",
            oidc_redirect_uri="https://platform.example.com/v1/auth/enterprise/callback",
        )
    ).status()
    assert ready.mode == "ready"
    assert ready.provider_name == "Example Identity"
    assert ready.issuer_url == "https://login.example.com/tenant"


def test_deployment_secrets_are_allowlisted_and_redacted_before_persistence() -> None:
    secrets = DeploymentSecrets(
        Settings(
            auth_bootstrap_secret="bootstrap-secret",
            oidc_client_secret="oidc-secret",
            github_connector_token="github-secret",
        )
    )

    assert secrets.get(SecretName.AUTH_BOOTSTRAP) == "bootstrap-secret"
    assert [status.configured for status in secrets.status().secrets] == [True, True, True]
    assert secrets.status().secrets[0].valid is False
    assert secrets.redact(
        {"message": "bootstrap-secret and github-secret", "nested": ["oidc-secret"]}
    ) == {"message": "[REDACTED] and [REDACTED]", "nested": ["[REDACTED]"]}


def test_security_audit_detail_schema_rejects_sensitive_and_unknown_fields() -> None:
    assert validate_audit_details(
        "authorization.denied", {"permission": "research.write"}
    ) == {"permission": "research.write"}

    with pytest.raises(AuditDetailPolicyError, match="sensitive"):
        validate_audit_details("auth.sign_in", {"password": "never-persist"})
    with pytest.raises(AuditDetailPolicyError, match="unapproved"):
        validate_audit_details("auth.sign_in", {"request_headers": {"cookie": "no"}})
    with pytest.raises(AuditDetailPolicyError, match="not registered"):
        validate_audit_details("connector.github.failed", {"reason": "no"})


def test_enterprise_identity_status_endpoint_never_returns_client_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.main.get_settings",
        lambda: Settings(
            oidc_issuer_url="https://login.example.com/tenant",
            oidc_client_id="platform-client",
            oidc_client_secret="not-exposed",
            oidc_redirect_uri="https://platform.example.com/v1/auth/enterprise/callback",
        ),
    )
    app = create_app()

    async def request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.get("/v1/auth/enterprise/status")

    response = asyncio.run(request())

    assert response.status_code == 200
    assert response.json()["mode"] == "ready"
    assert "client_secret" not in response.text
    assert "not-exposed" not in response.text


def test_service_identity_is_machine_scoped_and_cannot_manage_identities(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    administrator = AuthenticatedUser(
        id=uuid4(),
        email="admin@example.com",
        workspace_id=workspace_id,
        workspace_name="Workspace A",
        role="administrator",
        authenticated_at=datetime.now(UTC),
    )
    machine = AuthenticatedServiceIdentity(
        id=uuid4(),
        name="research-worker",
        workspace_id=workspace_id,
        workspace_name="Workspace A",
        permissions=frozenset({"research.read"}),
        authenticated_at=datetime.now(UTC),
    )

    class FakeIdentityService:
        async def current_user(self, token: str | None) -> AuthenticatedUser | None:
            return administrator if token == "admin-session" else None

        async def current_service_identity(
            self, authorization_header: str | None
        ) -> AuthenticatedServiceIdentity | None:
            return machine if authorization_header == "Bearer awi_si_test" else None

        async def create_service_identity(self, workspace, admin_id, name, permissions):
            assert workspace == workspace_id
            assert admin_id == administrator.id
            assert name == "research-worker"
            assert permissions == {"research.read"}
            return CreatedServiceIdentity(
                id=machine.id,
                name=name,
                workspace_id=workspace_id,
                permissions=frozenset(permissions),
                created_at=datetime.now(UTC),
                token="awi_si_returned-once",
            )

    class FakeResearchStore:
        async def list_runs(self, received_workspace_id, limit: int) -> list[object]:
            assert received_workspace_id == workspace_id
            assert limit == 25
            return []

    class FakeSecurityAuditStore:
        async def record(self, *_: object, **__: object) -> None:
            return None

    monkeypatch.setattr(
        "app.main.get_settings",
        lambda: Settings(database_url="postgresql://test", searxng_base_url=None),
    )
    app = create_app()
    app.state.identity_service = FakeIdentityService()
    app.state.research_store = FakeResearchStore()
    app.state.security_audit_store = FakeSecurityAuditStore()

    async def request() -> tuple[httpx.Response, httpx.Response, httpx.Response]:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            client.cookies.set("platform_session", "admin-session")
            created = await client.post(
                "/v1/service-identities",
                json={"name": "research-worker", "permissions": ["research.read"]},
            )
            client.cookies.clear()
            readable = await client.get(
                "/v1/research/runs", headers={"Authorization": "Bearer awi_si_test"}
            )
            denied = await client.get(
                "/v1/service-identities", headers={"Authorization": "Bearer awi_si_test"}
            )
            return created, readable, denied

    created, readable, denied = asyncio.run(request())
    assert created.status_code == 201
    assert created.json()["token"] == "awi_si_returned-once"
    assert readable.status_code == 200
    assert denied.status_code == 403


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

    class FakeSecurityAuditStore:
        def __init__(self) -> None:
            self.records: list[tuple[str, str, object, object, dict[str, object]]] = []

        async def record(
            self,
            event_type: str,
            outcome: str,
            actor_user_id=None,
            workspace_id=None,
            details: dict[str, object] | None = None,
        ) -> None:
            self.records.append(
                (event_type, outcome, actor_user_id, workspace_id, details or {})
            )

    monkeypatch.setattr(
        "app.main.get_settings",
        lambda: Settings(database_url="postgresql://test", searxng_base_url=None),
    )
    app = create_app()
    store = FakeResearchStore()
    app.state.identity_service = FakeIdentityService()
    app.state.research_store = store
    audit_store = FakeSecurityAuditStore()
    app.state.security_audit_store = audit_store

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
    assert audit_store.records == [
        (
            "authorization.denied",
            "denied",
            None,
            None,
            {"reason": "no_authenticated_identity"},
        ),
        (
            "authorization.denied",
            "denied",
            viewer.id,
            workspace_id,
            {"permission": "research.write"},
        ),
    ]


def test_security_audit_is_workspace_scoped_and_administrator_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    administrator = AuthenticatedUser(
        id=uuid4(),
        email="admin@example.com",
        workspace_id=workspace_id,
        workspace_name="Workspace A",
        role="administrator",
        authenticated_at=datetime.now(UTC),
    )

    class FakeIdentityService:
        async def current_user(self, token: str | None) -> AuthenticatedUser | None:
            return administrator if token == "admin-session" else None

    class FakeSecurityAuditStore:
        def __init__(self) -> None:
            self.workspace_id = None

        async def list_workspace_events(self, received_workspace_id, limit: int):
            self.workspace_id = received_workspace_id
            assert limit == 25
            return [
                SecurityAuditEvent(
                    id=uuid4(),
                    actor_user_id=administrator.id,
                    workspace_id=workspace_id,
                    event_type="auth.sign_in",
                    outcome="succeeded",
                    occurred_at=datetime.now(UTC),
                )
            ]

    monkeypatch.setattr(
        "app.main.get_settings",
        lambda: Settings(database_url="postgresql://test", searxng_base_url=None),
    )
    app = create_app()
    audit_store = FakeSecurityAuditStore()
    app.state.identity_service = FakeIdentityService()
    app.state.security_audit_store = audit_store

    async def request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            client.cookies.set("platform_session", "admin-session")
            return await client.get("/v1/audit/security")

    response = asyncio.run(request())

    assert response.status_code == 200
    assert audit_store.workspace_id == workspace_id
    assert response.json()["events"][0]["event_type"] == "auth.sign_in"
