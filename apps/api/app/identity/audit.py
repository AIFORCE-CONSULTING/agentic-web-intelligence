"""Append-only, schema-gated audit records for authentication and authorization events."""

import json
from collections.abc import Callable
from uuid import UUID, uuid4

import asyncpg

from app.identity.contracts import SecurityAuditEvent

_SENSITIVE_FIELD_MARKERS = frozenset(
    {"authorization", "cookie", "credential", "password", "secret", "token"}
)
_ALLOWED_DETAIL_FIELDS: dict[str, frozenset[str]] = {
    "auth.bootstrap": frozenset({"reason"}),
    "auth.sign_in": frozenset({"reason"}),
    "auth.sign_out": frozenset({"reason"}),
    "authorization.denied": frozenset({"permission", "reason"}),
    "service_identity.created": frozenset({"service_identity_id", "name"}),
    "service_identity.revoked": frozenset({"service_identity_id"}),
    "connector.github.draft_item.created": frozenset(
        {"project_number", "item_id", "priority"}
    ),
    "connector.github.draft_item.priority_updated": frozenset(
        {"project_number", "item_id", "priority"}
    ),
    "runtime.durable_execution.scheduled": frozenset({"run_id"}),
    "runtime.approval.approved": frozenset({"run_id"}),
    "runtime.approval.rejected": frozenset({"run_id"}),
    "runtime.durable_execution.cancelled": frozenset({"run_id"}),
}

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


class AuditDetailPolicyError(ValueError):
    """Raised when a record attempts to persist details outside its fixed schema."""


def validate_audit_details(event_type: str, details: dict[str, object] | None) -> dict[str, object]:
    """Allow only scalar, non-sensitive fields explicitly owned by an audit event type."""

    if event_type not in _ALLOWED_DETAIL_FIELDS:
        raise AuditDetailPolicyError(f"Audit event '{event_type}' is not registered.")
    candidate = details or {}
    for key in candidate:
        normalized_key = key.lower().replace("-", "_")
        if any(marker in normalized_key for marker in _SENSITIVE_FIELD_MARKERS):
            raise AuditDetailPolicyError(
                f"Audit field '{key}' is sensitive and cannot be persisted."
            )
    unknown = set(candidate) - _ALLOWED_DETAIL_FIELDS[event_type]
    if unknown:
        raise AuditDetailPolicyError(
            f"Audit event '{event_type}' contains unapproved fields: {', '.join(sorted(unknown))}."
        )
    for key, value in candidate.items():
        if not isinstance(value, str | int | float | bool | type(None)):
            raise AuditDetailPolicyError(f"Audit field '{key}' must be a scalar value.")
        if isinstance(value, str) and len(value) > 256:
            raise AuditDetailPolicyError(f"Audit field '{key}' exceeds the 256-character limit.")
    return dict(candidate)


class SecurityAuditStore:
    """Separate persistence boundary that never accepts secrets or raw session tokens."""

    def __init__(
        self,
        database_url: str | None,
        redact: Callable[[object], object] | None = None,
    ) -> None:
        self._database_url = database_url
        self._pool: asyncpg.Pool | None = None
        self._redact = redact or (lambda value: value)

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
        safe_details = validate_audit_details(event_type, details)
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
                json.dumps(self._redact(safe_details)),
            )

    async def healthcheck(self) -> None:
        """Confirm audit persistence is reachable without reading audit content."""

        pool = await self._connection_pool()
        async with pool.acquire() as connection:
            await connection.fetchval("SELECT 1")

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
