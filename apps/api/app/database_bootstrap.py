"""Explicit database bootstrap boundary for application schema readiness."""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
from typing import Literal

import asyncpg

from app.persistence import SCHEMA_SETUP_LOCK_ID
from app.settings import get_settings

BOOTSTRAP_NAME = "platform_application_schema"
SCHEMA_VERSION = "platform-schema:v2"

BOOTSTRAP_STATUS_SCHEMA = """
CREATE TABLE IF NOT EXISTS database_bootstrap_status (
    bootstrap_name TEXT PRIMARY KEY,
    schema_version TEXT NOT NULL,
    status TEXT NOT NULL CHECK (
        status IN ('not_run', 'initializing', 'ready', 'failed', 'incompatible')
    ),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    failure_reason TEXT
);
"""

BootstrapReadinessStatus = Literal[
    "not_run", "initializing", "ready", "failed", "incompatible", "unconfigured", "unavailable"
]


@dataclass(frozen=True)
class DatabaseBootstrapReadiness:
    """Safe operational readiness state for the platform database schema."""

    status: BootstrapReadinessStatus
    detail: str
    schema_version: str | None = None
    failure_reason: str | None = None

    @property
    def ready(self) -> bool:
        return self.status == "ready"


class DatabaseBootstrapError(RuntimeError):
    """Raised when the explicit bootstrap step cannot complete."""


def store_schema_fragments() -> list[tuple[str, str]]:
    """Return existing store-owned schema fragments in dependency order."""

    from app.agent_runtime.store import SCHEMA as AGENT_RUNTIME_SCHEMA
    from app.agentic_research.store import SCHEMA as AGENTIC_RESEARCH_SCHEMA
    from app.evidence_summaries.store import SCHEMA as EVIDENCE_SUMMARIES_SCHEMA
    from app.identity.audit import SCHEMA as SECURITY_AUDIT_SCHEMA
    from app.identity.store import SCHEMA as IDENTITY_SCHEMA
    from app.local_models.store import SCHEMA as LOCAL_MODELS_SCHEMA
    from app.web_research.store import SCHEMA as WEB_RESEARCH_SCHEMA
    from app.web_trust.store import SCHEMA as WEB_TRUST_SCHEMA

    return [
        ("identity", IDENTITY_SCHEMA),
        ("security_audit", SECURITY_AUDIT_SCHEMA),
        ("web_research", WEB_RESEARCH_SCHEMA),
        ("agent_runtime", AGENT_RUNTIME_SCHEMA),
        ("web_trust", WEB_TRUST_SCHEMA),
        ("evidence_summaries", EVIDENCE_SUMMARIES_SCHEMA),
        ("agentic_research", AGENTIC_RESEARCH_SCHEMA),
        ("local_models", LOCAL_MODELS_SCHEMA),
    ]


async def bootstrap_database(
    database_url: str | None,
    *,
    schema_version: str = SCHEMA_VERSION,
) -> DatabaseBootstrapReadiness:
    """Run all application schema setup before runtime work accepts traffic."""

    if not database_url:
        raise DatabaseBootstrapError("DATABASE_URL is required for database bootstrap.")
    pool: asyncpg.Pool | None = None
    try:
        pool = await asyncpg.create_pool(database_url, min_size=1, max_size=1)
        async with pool.acquire() as connection:
            await connection.execute("SELECT pg_advisory_lock($1)", SCHEMA_SETUP_LOCK_ID)
            try:
                await connection.execute(BOOTSTRAP_STATUS_SCHEMA)
                await _record_bootstrap_state(
                    connection,
                    status="initializing",
                    schema_version=schema_version,
                    failure_reason=None,
                    completed=False,
                )
                for _, schema in store_schema_fragments():
                    await connection.execute(schema)
                await _record_bootstrap_state(
                    connection,
                    status="ready",
                    schema_version=schema_version,
                    failure_reason=None,
                    completed=True,
                )
            except Exception as error:
                await _record_bootstrap_state(
                    connection,
                    status="failed",
                    schema_version=schema_version,
                    failure_reason=_safe_failure_reason(error),
                    completed=True,
                )
                raise
            finally:
                await connection.execute("SELECT pg_advisory_unlock($1)", SCHEMA_SETUP_LOCK_ID)
    except (asyncpg.PostgresError, OSError) as error:
        raise DatabaseBootstrapError("Database bootstrap failed.") from error
    finally:
        if pool is not None:
            await pool.close()
    return await database_bootstrap_readiness(database_url, schema_version=schema_version)


async def database_bootstrap_readiness(
    database_url: str | None,
    *,
    schema_version: str = SCHEMA_VERSION,
) -> DatabaseBootstrapReadiness:
    """Read database bootstrap readiness without running schema setup."""

    if not database_url:
        return DatabaseBootstrapReadiness(
            status="unconfigured",
            detail="Database persistence is not configured.",
        )
    pool: asyncpg.Pool | None = None
    try:
        pool = await asyncpg.create_pool(database_url, min_size=1, max_size=1)
        async with pool.acquire() as connection:
            table_exists = await connection.fetchval(
                "SELECT to_regclass('public.database_bootstrap_status') IS NOT NULL"
            )
            if not table_exists:
                return DatabaseBootstrapReadiness(
                    status="not_run",
                    detail="Database bootstrap has not run.",
                )
            row = await connection.fetchrow(
                """
                SELECT schema_version, status, failure_reason
                FROM database_bootstrap_status
                WHERE bootstrap_name = $1
                """,
                BOOTSTRAP_NAME,
            )
            if row is None:
                return DatabaseBootstrapReadiness(
                    status="not_run",
                    detail="Database bootstrap readiness has not been recorded.",
                )
            recorded_version = row["schema_version"]
            if row["status"] == "ready" and recorded_version != schema_version:
                return DatabaseBootstrapReadiness(
                    status="incompatible",
                    schema_version=recorded_version,
                    detail=(
                        "Database bootstrap is for a different application schema version."
                    ),
                )
            status = row["status"]
            return DatabaseBootstrapReadiness(
                status=status,
                schema_version=recorded_version,
                failure_reason=row["failure_reason"],
                detail=_readiness_detail(status, row["failure_reason"]),
            )
    except (asyncpg.PostgresError, OSError) as error:
        return DatabaseBootstrapReadiness(
            status="unavailable",
            detail="Database bootstrap readiness could not be checked.",
            failure_reason=_safe_failure_reason(error),
        )
    finally:
        if pool is not None:
            await pool.close()


async def require_database_bootstrap_ready(database_url: str | None) -> None:
    """Fail startup when schema bootstrap has not completed successfully."""

    readiness = await database_bootstrap_readiness(database_url)
    if not readiness.ready:
        raise DatabaseBootstrapError(readiness.detail)


async def _record_bootstrap_state(
    connection: asyncpg.Connection,
    *,
    status: Literal["initializing", "ready", "failed"],
    schema_version: str,
    failure_reason: str | None,
    completed: bool,
) -> None:
    await connection.execute(
        """
        INSERT INTO database_bootstrap_status (
            bootstrap_name, schema_version, status, started_at, completed_at, failure_reason
        )
        VALUES ($1, $2, $3, now(), CASE WHEN $4 THEN now() ELSE NULL END, $5)
        ON CONFLICT (bootstrap_name) DO UPDATE SET
            schema_version = EXCLUDED.schema_version,
            status = EXCLUDED.status,
            started_at = CASE
                WHEN EXCLUDED.status = 'initializing' THEN EXCLUDED.started_at
                ELSE database_bootstrap_status.started_at
            END,
            completed_at = EXCLUDED.completed_at,
            failure_reason = EXCLUDED.failure_reason
        """,
        BOOTSTRAP_NAME,
        schema_version,
        status,
        completed,
        failure_reason,
    )


def _readiness_detail(status: str, failure_reason: str | None) -> str:
    if status == "ready":
        return "Database bootstrap completed and runtime work may proceed."
    if status == "initializing":
        return "Database bootstrap is still running."
    if status == "failed":
        return failure_reason or "Database bootstrap failed."
    if status == "incompatible":
        return "Database bootstrap is incompatible with this application version."
    return "Database bootstrap has not completed."


def _safe_failure_reason(error: BaseException) -> str:
    message = str(error).strip()
    return message[:500] if message else error.__class__.__name__


async def _main() -> None:
    parser = argparse.ArgumentParser(description="Prepare platform database schema.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check readiness without bootstrapping.",
    )
    args = parser.parse_args()
    settings = get_settings()
    if args.check:
        readiness = await database_bootstrap_readiness(settings.database_url)
    else:
        readiness = await bootstrap_database(settings.database_url)
    if not readiness.ready:
        raise SystemExit(readiness.detail)
    print(readiness.detail)


if __name__ == "__main__":
    asyncio.run(_main())
