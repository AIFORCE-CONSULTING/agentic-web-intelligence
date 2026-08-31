"""Postgres-backed, append-only records for governed research runs."""

import json
from uuid import UUID, uuid4

import asyncpg

from app.web_research.contracts import (
    AuditEvent,
    Evidence,
    McpToolAuditEvent,
    ResearchRun,
    ResearchRunSummary,
    ResearchStoreUnavailable,
    SourceCandidate,
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS research_runs (
    id UUID PRIMARY KEY,
    question TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('searching', 'ready', 'failed')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS research_sources (
    id UUID PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES research_runs(id) ON DELETE CASCADE,
    rank INTEGER NOT NULL CHECK (rank > 0),
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    snippet TEXT NOT NULL DEFAULT '',
    engine TEXT,
    UNIQUE (run_id, rank)
);
CREATE TABLE IF NOT EXISTS research_evidence (
    id UUID PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES research_runs(id) ON DELETE CASCADE,
    url TEXT NOT NULL,
    retrieved_at TIMESTAMPTZ NOT NULL,
    content_type TEXT NOT NULL,
    text TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    extraction_method TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS research_audit_events (
    id UUID PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES research_runs(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    details JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE TABLE IF NOT EXISTS mcp_tool_audit_events (
    id UUID PRIMARY KEY,
    request_id TEXT,
    tool_name TEXT NOT NULL,
    outcome TEXT NOT NULL CHECK (outcome IN ('succeeded', 'failed', 'denied')),
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    details JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS research_sources_run_id_idx ON research_sources(run_id, rank);
CREATE INDEX IF NOT EXISTS research_evidence_run_id_idx ON research_evidence(run_id, retrieved_at);
CREATE INDEX IF NOT EXISTS research_audit_events_run_id_idx
    ON research_audit_events(run_id, occurred_at);
CREATE INDEX IF NOT EXISTS mcp_tool_audit_events_occurred_at_idx
    ON mcp_tool_audit_events(occurred_at DESC);
"""


class ResearchStore:
    """Lazy Postgres store so API startup does not race optional Compose services."""

    def __init__(self, database_url: str | None) -> None:
        self._database_url = database_url
        self._pool: asyncpg.Pool | None = None

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    async def _connection_pool(self) -> asyncpg.Pool:
        if not self._database_url:
            raise ResearchStoreUnavailable("Research persistence is not configured.")
        if self._pool is None:
            try:
                self._pool = await asyncpg.create_pool(self._database_url, min_size=1, max_size=5)
                async with self._pool.acquire() as connection:
                    await connection.execute(SCHEMA)
            except (asyncpg.PostgresError, OSError) as error:
                if self._pool is not None:
                    await self._pool.close()
                    self._pool = None
                raise ResearchStoreUnavailable("Research persistence is unavailable.") from error
        return self._pool

    async def create_run(self, question: str) -> ResearchRun:
        run_id = uuid4()
        pool = await self._connection_pool()
        async with pool.acquire() as connection:
            row = await connection.fetchrow(
                """INSERT INTO research_runs (id, question, status)
                   VALUES ($1, $2, 'searching')
                   RETURNING id, question, status, created_at, updated_at""",
                run_id,
                question,
            )
            await self._append_audit(
                connection, run_id, "research.run.created", {"question": question}
            )
        return ResearchRun(**dict(row))

    async def healthcheck(self) -> None:
        """Confirm that the configured persistence store accepts a trivial query."""

        pool = await self._connection_pool()
        async with pool.acquire() as connection:
            await connection.fetchval("SELECT 1")

    async def record_mcp_tool_event(
        self, request_id: str | None, tool_name: str, outcome: str, details: dict[str, object]
    ) -> None:
        """Append one direct MCP execution outcome without creating a research run."""

        pool = await self._connection_pool()
        async with pool.acquire() as connection:
            await connection.execute(
                """INSERT INTO mcp_tool_audit_events (id, request_id, tool_name, outcome, details)
                   VALUES ($1, $2, $3, $4, $5::jsonb)""",
                uuid4(),
                request_id,
                tool_name,
                outcome,
                json.dumps(details),
            )

    async def list_mcp_tool_events(self, limit: int) -> list[McpToolAuditEvent]:
        """Return recent direct MCP outcomes without retaining retrieved page content."""

        pool = await self._connection_pool()
        async with pool.acquire() as connection:
            rows = await connection.fetch(
                """SELECT id, request_id, tool_name, outcome, occurred_at, details
                   FROM mcp_tool_audit_events ORDER BY occurred_at DESC LIMIT $1""",
                limit,
            )
        events: list[McpToolAuditEvent] = []
        for row in rows:
            event = dict(row)
            event["details"] = self._details(row["details"])
            events.append(McpToolAuditEvent(**event))
        return events

    async def save_sources(self, run_id: UUID, sources: list[SourceCandidate]) -> None:
        pool = await self._connection_pool()
        async with pool.acquire() as connection, connection.transaction():
            for source in sources:
                await connection.execute(
                    """INSERT INTO research_sources (id, run_id, rank, title, url, snippet, engine)
                       VALUES ($1, $2, $3, $4, $5, $6, $7)""",
                    uuid4(),
                    run_id,
                    source.rank,
                    source.title,
                    source.url,
                    source.snippet,
                    source.engine,
                )
            await self._append_audit(
                connection, run_id, "research.search.completed", {"source_count": len(sources)}
            )
            await connection.execute(
                "UPDATE research_runs SET status = 'ready', updated_at = now() WHERE id = $1",
                run_id,
            )

    async def save_evidence(self, run_id: UUID, evidence: Evidence) -> None:
        pool = await self._connection_pool()
        async with pool.acquire() as connection, connection.transaction():
            exists = await connection.fetchval("SELECT 1 FROM research_runs WHERE id = $1", run_id)
            if not exists:
                raise KeyError(run_id)
            await connection.execute(
                """INSERT INTO research_evidence
                   (id, run_id, url, retrieved_at, content_type, text, content_hash,
                    extraction_method)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8)""",
                uuid4(),
                run_id,
                evidence.url,
                evidence.retrieved_at,
                evidence.content_type,
                evidence.text,
                evidence.content_hash,
                evidence.extraction_method,
            )
            await self._append_audit(
                connection, run_id, "research.evidence.extracted",
                {"url": evidence.url, "content_hash": evidence.content_hash},
            )
            await connection.execute(
                "UPDATE research_runs SET updated_at = now() WHERE id = $1", run_id
            )

    async def run_exists(self, run_id: UUID) -> bool:
        """Confirm a run exists before invoking an external retrieval action for it."""

        pool = await self._connection_pool()
        async with pool.acquire() as connection:
            return bool(
                await connection.fetchval("SELECT 1 FROM research_runs WHERE id = $1", run_id)
            )

    async def record_policy_denial(
        self, run_id: UUID, requested_url: str, reason: str
    ) -> None:
        """Append a denial event without storing untrusted response content."""

        pool = await self._connection_pool()
        async with pool.acquire() as connection, connection.transaction():
            await self._append_audit(
                connection,
                run_id,
                "research.extract.denied",
                {"requested_url": requested_url, "reason": reason},
            )
            await connection.execute(
                "UPDATE research_runs SET updated_at = now() WHERE id = $1", run_id
            )

    async def record_extraction_failure(
        self, run_id: UUID, requested_url: str, reason: str, upstream_status: int | None
    ) -> None:
        """Append a source-retrieval failure without storing untrusted response content."""

        pool = await self._connection_pool()
        async with pool.acquire() as connection, connection.transaction():
            await self._append_audit(
                connection,
                run_id,
                "research.extract.failed",
                {
                    "requested_url": requested_url,
                    "reason": reason,
                    "upstream_status": upstream_status,
                },
            )
            await connection.execute(
                "UPDATE research_runs SET updated_at = now() WHERE id = $1", run_id
            )

    async def record_batch_extraction_started(self, run_id: UUID, urls: list[str]) -> None:
        """Record the ordered candidate selection before retrieval begins."""

        pool = await self._connection_pool()
        async with pool.acquire() as connection, connection.transaction():
            await self._append_audit(
                connection,
                run_id,
                "research.batch.extract.started",
                {"selected_count": len(urls), "urls": urls},
            )
            await connection.execute(
                "UPDATE research_runs SET updated_at = now() WHERE id = $1", run_id
            )

    async def record_batch_extraction_completed(
        self, run_id: UUID, succeeded: int, failed: int, denied: int
    ) -> None:
        """Record the batch summary after every selected source has been attempted."""

        pool = await self._connection_pool()
        async with pool.acquire() as connection, connection.transaction():
            await self._append_audit(
                connection,
                run_id,
                "research.batch.extract.completed",
                {
                    "selected_count": succeeded + failed + denied,
                    "succeeded_count": succeeded,
                    "failed_count": failed,
                    "denied_count": denied,
                },
            )
            await connection.execute(
                "UPDATE research_runs SET updated_at = now() WHERE id = $1", run_id
            )

    async def mark_failed(self, run_id: UUID, reason: str) -> None:
        pool = await self._connection_pool()
        async with pool.acquire() as connection, connection.transaction():
            await self._append_audit(
                connection, run_id, "research.search.failed", {"reason": reason}
            )
            await connection.execute(
                "UPDATE research_runs SET status = 'failed', updated_at = now() WHERE id = $1",
                run_id,
            )

    async def get_run(self, run_id: UUID) -> ResearchRun | None:
        pool = await self._connection_pool()
        async with pool.acquire() as connection:
            run = await connection.fetchrow("SELECT * FROM research_runs WHERE id = $1", run_id)
            if run is None:
                return None
            sources = await connection.fetch(
                """SELECT rank, title, url, snippet, engine FROM research_sources
                   WHERE run_id = $1 ORDER BY rank""",
                run_id,
            )
            evidence = await connection.fetch(
                """SELECT url, retrieved_at, content_type, text, content_hash, extraction_method
                   FROM research_evidence WHERE run_id = $1 ORDER BY retrieved_at""", run_id
            )
            events = await connection.fetch(
                """SELECT event_type, occurred_at, details FROM research_audit_events
                   WHERE run_id = $1 ORDER BY occurred_at""", run_id
            )
        return ResearchRun(
            **dict(run),
            sources=[SourceCandidate(**dict(row)) for row in sources],
            evidence=[Evidence(**dict(row)) for row in evidence],
            audit_events=[
                AuditEvent(
                    event_type=row["event_type"],
                    occurred_at=row["occurred_at"],
                    details=self._details(row["details"]),
                )
                for row in events
            ],
        )

    async def list_runs(self, limit: int) -> list[ResearchRunSummary]:
        """Return a bounded run library without loading evidence text into the list view."""

        pool = await self._connection_pool()
        async with pool.acquire() as connection:
            rows = await connection.fetch(
                """SELECT runs.id, runs.question, runs.status, runs.created_at, runs.updated_at,
                          COUNT(DISTINCT sources.id)::integer AS source_count,
                          COUNT(DISTINCT evidence.id)::integer AS evidence_count
                   FROM research_runs AS runs
                   LEFT JOIN research_sources AS sources ON sources.run_id = runs.id
                   LEFT JOIN research_evidence AS evidence ON evidence.run_id = runs.id
                   GROUP BY runs.id
                   ORDER BY runs.updated_at DESC
                   LIMIT $1""",
                limit,
            )
        return [ResearchRunSummary(**dict(row)) for row in rows]

    @staticmethod
    async def _append_audit(
        connection: asyncpg.Connection, run_id: UUID, event_type: str, details: dict[str, object]
    ) -> None:
        await connection.execute(
            """INSERT INTO research_audit_events (id, run_id, event_type, details)
               VALUES ($1, $2, $3, $4::jsonb)""",
            uuid4(),
            run_id,
            event_type,
            json.dumps(details),
        )

    @staticmethod
    def _details(value: object) -> dict[str, object]:
        return json.loads(value) if isinstance(value, str) else dict(value)
