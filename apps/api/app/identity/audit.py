"""Append-only, sanitized audit records for authentication and authorization events."""

import json
from uuid import UUID, uuid4

import asyncpg

from app.identity.contracts import SecurityAuditEvent

SCHEMA = """
CREATE TABLE IF NOT EXISTS security_audit_events (
    id UUID PRIMARY KEY,
    actor_user_id UUID,
    actor_service_identity_id UUID,
    workspace_id UUID,
    event_type TEXT NOT NULL,
    outcome TEXT NOT NULL CHECK (outcome IN ('succeeded', 'denied')),
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    details JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS security_audit_events_workspace_occurred_at_idx
    ON security_audit_events(workspace_id, occurred_at DESC);
ALTER TABLE security_audit_events ADD COLUMN IF NOT EXISTS actor_service_identity_id UUID;
"""


class SecurityAuditStoreUnavailable(RuntimeError):
    """Raised when audit persistence cannot be reached."""


class SecurityAuditStore:
    """Separate persistence boundary that never accepts secrets or raw session tokens."""

    def __init__(self, database_url: str | None) -> None:
        self._database_url = database_url
        self._pool: asyncpg.Pool | None = None

    async def _connection_pool(self) -> asyncpg.Pool:
        if not self._database_url:
            raise SecurityAuditStoreUnavailable("Security audit persistence is not configured.")
        if self._pool is None:
            try:
                self._pool = await asyncpg.create_pool(self._database_url, min_size=1, max_size=5)
                async with self._pool.acquire() as connection:
                    await connection.execute(SCHEMA)
            except (asyncpg.PostgresError, OSError) as error:
                if self._pool is not None:
                    await self._pool.close()
                    self._pool = None
                raise SecurityAuditStoreUnavailable(
                    "Security audit persistence is unavailable."
                ) from error
        return self._pool

    async def record(
        self,
        event_type: str,
        outcome: str,
        actor_user_id: UUID | None = None,
        actor_service_identity_id: UUID | None = None,
        workspace_id: UUID | None = None,
        details: dict[str, object] | None = None,
    ) -> None:
        pool = await self._connection_pool()
        async with pool.acquire() as connection:
            await connection.execute(
                """INSERT INTO security_audit_events
                (id, actor_user_id, actor_service_identity_id, workspace_id,
                event_type, outcome, details)
                VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb)""",
                uuid4(),
                actor_user_id,
                actor_service_identity_id,
                workspace_id,
                event_type,
                outcome,
                json.dumps(details or {}),
            )

    async def list_workspace_events(
        self, workspace_id: UUID, limit: int
    ) -> list[SecurityAuditEvent]:
        pool = await self._connection_pool()
        async with pool.acquire() as connection:
            rows = await connection.fetch(
                """SELECT id, actor_user_id, actor_service_identity_id, workspace_id,
                event_type, outcome, occurred_at, details
                FROM security_audit_events WHERE workspace_id = $1
                ORDER BY occurred_at DESC LIMIT $2""",
                workspace_id,
                limit,
            )
        events: list[SecurityAuditEvent] = []
        for row in rows:
            event = dict(row)
            event["details"] = (
                json.loads(row["details"])
                if isinstance(row["details"], str)
                else dict(row["details"])
            )
            events.append(SecurityAuditEvent(**event))
        return events
