"""Shared Postgres persistence helpers."""

import asyncpg

SCHEMA_SETUP_LOCK_ID = 4_282_026_001


async def execute_schema_setup(connection: asyncpg.Connection, schema: str) -> None:
    """Run store schema setup one store at a time across API and worker processes."""

    await connection.execute("SELECT pg_advisory_lock($1)", SCHEMA_SETUP_LOCK_ID)
    try:
        await connection.execute(schema)
    finally:
        await connection.execute("SELECT pg_advisory_unlock($1)", SCHEMA_SETUP_LOCK_ID)
