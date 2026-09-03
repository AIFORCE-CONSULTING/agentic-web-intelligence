"""PostgreSQL persistence for local identities, memberships, and revocable sessions."""

import hashlib
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import asyncpg

from app.identity.contracts import AuthenticatedUser

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
    token_hash TEXT NOT NULL UNIQUE,
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS user_sessions_token_hash_idx ON user_sessions(token_hash);
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

    async def create_session(self, user_id: UUID, token: str) -> None:
        pool = await self._connection_pool()
        async with pool.acquire() as connection:
            await connection.execute(
                """INSERT INTO user_sessions (id, user_id, token_hash, expires_at)
                VALUES ($1, $2, $3, $4)""",
                uuid4(),
                user_id,
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
                JOIN workspace_memberships AS memberships ON memberships.user_id = users.id
                JOIN workspaces ON workspaces.id = memberships.workspace_id
                WHERE sessions.token_hash = $1 AND sessions.revoked_at IS NULL
                AND sessions.expires_at > now()
                AND users.is_active = TRUE ORDER BY memberships.created_at LIMIT 1""",
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


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
