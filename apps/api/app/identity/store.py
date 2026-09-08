"""PostgreSQL persistence for local identities, memberships, and revocable sessions."""

import hashlib
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import asyncpg

from app.identity.contracts import (
    AuthenticatedServiceIdentity,
    AuthenticatedUser,
    ServiceIdentityInfo,
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS workspaces (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS platform_users (
    id UUID PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    auth_provider TEXT NOT NULL DEFAULT 'local',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS workspace_memberships (
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES platform_users(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('administrator', 'operator', 'viewer')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (workspace_id, user_id)
);
CREATE TABLE IF NOT EXISTS user_sessions (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES platform_users(id) ON DELETE CASCADE,
    workspace_id UUID REFERENCES workspaces(id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL UNIQUE,
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS user_sessions_token_hash_idx ON user_sessions(token_hash);
ALTER TABLE user_sessions ADD COLUMN IF NOT EXISTS workspace_id UUID;
CREATE INDEX IF NOT EXISTS user_sessions_workspace_id_idx ON user_sessions(workspace_id);
CREATE TABLE IF NOT EXISTS service_identities (
    id UUID PRIMARY KEY,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    token_hash TEXT NOT NULL UNIQUE,
    permissions JSONB NOT NULL,
    created_by_user_id UUID NOT NULL REFERENCES platform_users(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    revoked_at TIMESTAMPTZ,
    UNIQUE (workspace_id, name)
);
CREATE INDEX IF NOT EXISTS service_identities_token_hash_idx ON service_identities(token_hash);
CREATE INDEX IF NOT EXISTS service_identities_workspace_created_at_idx
    ON service_identities(workspace_id, created_at DESC);
"""

SESSION_LIFETIME = timedelta(hours=8)


class IdentityStoreUnavailable(RuntimeError):
    """Raised when identity persistence cannot be reached."""


class IdentityStore:
    """Durable, server-side identity data; raw session tokens are never retained."""

    def __init__(self, database_url: str | None) -> None:
        self._database_url = database_url
        self._pool: asyncpg.Pool | None = None

    async def _connection_pool(self) -> asyncpg.Pool:
        if not self._database_url:
            raise IdentityStoreUnavailable("Identity persistence is not configured.")
        if self._pool is None:
            try:
                self._pool = await asyncpg.create_pool(self._database_url, min_size=1, max_size=5)
                async with self._pool.acquire() as connection:
                    await connection.execute(SCHEMA)
            except (asyncpg.PostgresError, OSError) as error:
                if self._pool is not None:
                    await self._pool.close()
                    self._pool = None
                raise IdentityStoreUnavailable("Identity persistence is unavailable.") from error
        return self._pool

    async def has_users(self) -> bool:
        pool = await self._connection_pool()
        async with pool.acquire() as connection:
            return bool(await connection.fetchval("SELECT EXISTS(SELECT 1 FROM platform_users)"))

    async def healthcheck(self) -> None:
        """Confirm identity persistence is reachable without disclosing identity data."""

        pool = await self._connection_pool()
        async with pool.acquire() as connection:
            await connection.fetchval("SELECT 1")

    async def create_bootstrap_admin(self, email: str, password_hash: str) -> AuthenticatedUser:
        pool = await self._connection_pool()
        user_id, workspace_id = uuid4(), uuid4()
        async with pool.acquire() as connection, connection.transaction():
            if await connection.fetchval("SELECT EXISTS(SELECT 1 FROM platform_users FOR UPDATE)"):
                raise ValueError("A local administrator has already been initialized.")
            await connection.execute(
                "INSERT INTO workspaces (id, name) VALUES ($1, $2)",
                workspace_id,
                "Default workspace",
            )
            await connection.execute(
                "INSERT INTO platform_users (id, email, password_hash) VALUES ($1, $2, $3)",
                user_id,
                email.lower(),
                password_hash,
            )
            await connection.execute(
                """INSERT INTO workspace_memberships (workspace_id, user_id, role)
                VALUES ($1, $2, 'administrator')""",
                workspace_id,
                user_id,
            )
        return AuthenticatedUser(
            id=user_id,
            email=email.lower(),
            workspace_id=workspace_id,
            workspace_name="Default workspace",
            role="administrator",
            authenticated_at=datetime.now(UTC),
        )

    async def authenticate_local(self, email: str) -> tuple[UUID, str] | None:
        pool = await self._connection_pool()
        async with pool.acquire() as connection:
            row = await connection.fetchrow(
                """SELECT id, password_hash FROM platform_users
                WHERE email = $1 AND auth_provider = 'local' AND is_active = TRUE""",
                email.lower(),
            )
        return (row["id"], row["password_hash"]) if row is not None else None

    async def get_local_user_workspace(self, user_id: UUID) -> UUID | None:
        """Select the sole local workspace membership for this initial Phase 4 slice."""

        pool = await self._connection_pool()
        async with pool.acquire() as connection:
            return await connection.fetchval(
                "SELECT workspace_id FROM workspace_memberships "
                "WHERE user_id = $1 ORDER BY created_at LIMIT 1",
                user_id,
            )

    async def create_session(self, user_id: UUID, workspace_id: UUID, token: str) -> None:
        pool = await self._connection_pool()
        async with pool.acquire() as connection:
            await connection.execute(
                """INSERT INTO user_sessions (id, user_id, workspace_id, token_hash, expires_at)
                VALUES ($1, $2, $3, $4, $5)""",
                uuid4(),
                user_id,
                workspace_id,
                _token_hash(token),
                datetime.now(UTC) + SESSION_LIFETIME,
            )

    async def get_session_user(self, token: str) -> AuthenticatedUser | None:
        pool = await self._connection_pool()
        async with pool.acquire() as connection:
            row = await connection.fetchrow(
                """SELECT users.id, users.email, memberships.workspace_id,
                workspaces.name AS workspace_name,
                memberships.role, sessions.created_at
                FROM user_sessions AS sessions
                JOIN platform_users AS users ON users.id = sessions.user_id
                JOIN workspace_memberships AS memberships
                    ON memberships.user_id = users.id
                    AND memberships.workspace_id = sessions.workspace_id
                JOIN workspaces ON workspaces.id = memberships.workspace_id
                WHERE sessions.token_hash = $1 AND sessions.revoked_at IS NULL
                AND sessions.expires_at > now()
                AND users.is_active = TRUE""",
                _token_hash(token),
            )
        if row is None:
            return None
        return AuthenticatedUser(
            id=row["id"],
            email=row["email"],
            workspace_id=row["workspace_id"],
            workspace_name=row["workspace_name"],
            role=row["role"],
            authenticated_at=row["created_at"],
        )

    async def revoke_session(self, token: str) -> None:
        pool = await self._connection_pool()
        async with pool.acquire() as connection:
            await connection.execute(
                "UPDATE user_sessions SET revoked_at = now() "
                "WHERE token_hash = $1 AND revoked_at IS NULL",
                _token_hash(token),
            )

    async def create_service_identity(
        self,
        workspace_id: UUID,
        name: str,
        permissions: frozenset[str],
        created_by_user_id: UUID,
        token: str,
    ) -> ServiceIdentityInfo:
        pool = await self._connection_pool()
        identity_id = uuid4()
        async with pool.acquire() as connection:
            try:
                row = await connection.fetchrow(
                    """INSERT INTO service_identities
                    (id, workspace_id, name, token_hash, permissions, created_by_user_id)
                    VALUES ($1, $2, $3, $4, $5::jsonb, $6)
                    RETURNING id, name, workspace_id, permissions, created_at, revoked_at""",
                    identity_id,
                    workspace_id,
                    name,
                    _token_hash(token),
                    json.dumps(sorted(permissions)),
                    created_by_user_id,
                )
            except asyncpg.UniqueViolationError as error:
                raise ValueError(
                    "A service identity with this name already exists in the workspace."
                ) from error
        return _service_identity_info(row)

    async def get_service_identity(self, token: str) -> AuthenticatedServiceIdentity | None:
        pool = await self._connection_pool()
        async with pool.acquire() as connection:
            row = await connection.fetchrow(
                """SELECT identities.id, identities.name, identities.workspace_id,
                workspaces.name AS workspace_name,
                identities.permissions, identities.created_at
                FROM service_identities AS identities
                JOIN workspaces ON workspaces.id = identities.workspace_id
                WHERE identities.token_hash = $1 AND identities.revoked_at IS NULL""",
                _token_hash(token),
            )
        if row is None:
            return None
        return AuthenticatedServiceIdentity(
            id=row["id"],
            name=row["name"],
            workspace_id=row["workspace_id"],
            workspace_name=row["workspace_name"],
            permissions=frozenset(_permissions(row["permissions"])),
            authenticated_at=row["created_at"],
        )

    async def list_service_identities(
        self, workspace_id: UUID, limit: int
    ) -> list[ServiceIdentityInfo]:
        pool = await self._connection_pool()
        async with pool.acquire() as connection:
            rows = await connection.fetch(
                """SELECT id, name, workspace_id, permissions, created_at, revoked_at
                FROM service_identities WHERE workspace_id = $1
                ORDER BY created_at DESC LIMIT $2""",
                workspace_id,
                limit,
            )
        return [_service_identity_info(row) for row in rows]

    async def revoke_service_identity(self, identity_id: UUID, workspace_id: UUID) -> bool:
        pool = await self._connection_pool()
        async with pool.acquire() as connection:
            result = await connection.execute(
                """UPDATE service_identities SET revoked_at = now()
                WHERE id = $1 AND workspace_id = $2 AND revoked_at IS NULL""",
                identity_id,
                workspace_id,
            )
        return result == "UPDATE 1"


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _permissions(value: object) -> list[str]:
    return json.loads(value) if isinstance(value, str) else list(value)


def _service_identity_info(row: asyncpg.Record) -> ServiceIdentityInfo:
    return ServiceIdentityInfo(
        id=row["id"],
        name=row["name"],
        workspace_id=row["workspace_id"],
        permissions=frozenset(_permissions(row["permissions"])),
        created_at=row["created_at"],
        revoked_at=row["revoked_at"],
    )
