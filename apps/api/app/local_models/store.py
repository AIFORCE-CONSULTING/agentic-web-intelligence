"""Workspace-scoped persistence for non-secret local model settings."""

from uuid import UUID

import asyncpg

from app.local_models.contracts import LocalModelProviderConfiguration

SCHEMA = """
CREATE TABLE IF NOT EXISTS local_model_provider_configurations (
    workspace_id UUID PRIMARY KEY REFERENCES workspaces(id) ON DELETE CASCADE,
    endpoint_url TEXT NOT NULL,
    model_name TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


class LocalModelProviderStoreUnavailable(RuntimeError):
    """Raised when the configured Postgres store is unreachable."""


class LocalModelProviderStore:
    def __init__(self, database_url: str | None) -> None:
        self._database_url = database_url
        self._pool: asyncpg.Pool | None = None

    async def _connection_pool(self) -> asyncpg.Pool:
        if not self._database_url:
            raise LocalModelProviderStoreUnavailable(
                "Local model configuration persistence is not configured."
            )
        if self._pool is None:
            try:
                self._pool = await asyncpg.create_pool(self._database_url, min_size=1, max_size=5)
                async with self._pool.acquire() as connection:
                    await connection.execute(SCHEMA)
            except (asyncpg.PostgresError, OSError) as error:
                if self._pool is not None:
                    await self._pool.close()
                    self._pool = None
                raise LocalModelProviderStoreUnavailable(
                    "Local model configuration persistence is unavailable."
                ) from error
        return self._pool

    async def get(self, workspace_id: UUID) -> LocalModelProviderConfiguration | None:
        pool = await self._connection_pool()
        async with pool.acquire() as connection:
            row = await connection.fetchrow(
                "SELECT workspace_id, endpoint_url, model_name, updated_at "
                "FROM local_model_provider_configurations WHERE workspace_id = $1",
                workspace_id,
            )
        return LocalModelProviderConfiguration(**dict(row)) if row else None

    async def save(
        self, workspace_id: UUID, endpoint_url: str, model_name: str
    ) -> LocalModelProviderConfiguration:
        pool = await self._connection_pool()
        async with pool.acquire() as connection:
            row = await connection.fetchrow(
                """INSERT INTO local_model_provider_configurations
                (workspace_id, endpoint_url, model_name) VALUES ($1, $2, $3)
                ON CONFLICT (workspace_id) DO UPDATE SET endpoint_url = EXCLUDED.endpoint_url,
                model_name = EXCLUDED.model_name, updated_at = now()
                RETURNING workspace_id, endpoint_url, model_name, updated_at""",
                workspace_id,
                endpoint_url,
                model_name,
            )
        return LocalModelProviderConfiguration(**dict(row))
