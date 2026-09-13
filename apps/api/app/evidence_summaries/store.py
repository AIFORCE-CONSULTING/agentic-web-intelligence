"""Canonical, workspace-scoped evidence-summary execution records."""

import json
from uuid import UUID, uuid4

import asyncpg

from app.evidence_summaries.contracts import (
    EvidenceSummaryExecution,
    EvidenceSummaryExecutionSource,
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS evidence_summary_executions (
    id UUID PRIMARY KEY,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    run_id UUID NOT NULL REFERENCES research_runs(id) ON DELETE CASCADE,
    route TEXT NOT NULL CHECK (route IN ('undetermined', 'direct', 'durable'))
        DEFAULT 'undetermined',
    status TEXT NOT NULL CHECK (
        status IN ('pending', 'extracting', 'awaiting_execution', 'summarizing',
                   'completed', 'failed', 'cancelled')
    ) DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS evidence_summary_execution_sources (
    execution_id UUID NOT NULL REFERENCES evidence_summary_executions(id) ON DELETE CASCADE,
    url TEXT NOT NULL,
    status TEXT NOT NULL CHECK (
        status IN ('pending', 'extracting', 'extracted', 'summarizing', 'completed',
                   'failed', 'cancelled')
    ) DEFAULT 'pending',
    content_hash TEXT,
    chunk_count INTEGER,
    summary TEXT,
    keywords JSONB,
    failure_reason TEXT,
    PRIMARY KEY (execution_id, url)
);
ALTER TABLE evidence_summary_executions ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ
    NOT NULL DEFAULT now();
ALTER TABLE evidence_summary_execution_sources ADD COLUMN IF NOT EXISTS summary TEXT;
ALTER TABLE evidence_summary_execution_sources ADD COLUMN IF NOT EXISTS keywords JSONB;
ALTER TABLE evidence_summary_execution_sources ADD COLUMN IF NOT EXISTS failure_reason TEXT;
ALTER TABLE evidence_summary_executions
    DROP CONSTRAINT IF EXISTS evidence_summary_executions_status_check;
ALTER TABLE evidence_summary_executions
    ADD CONSTRAINT evidence_summary_executions_status_check CHECK (
        status IN ('pending', 'extracting', 'awaiting_execution', 'summarizing',
                   'completed', 'failed', 'cancelled')
    );
ALTER TABLE evidence_summary_execution_sources
    DROP CONSTRAINT IF EXISTS evidence_summary_execution_sources_status_check;
ALTER TABLE evidence_summary_execution_sources
    ADD CONSTRAINT evidence_summary_execution_sources_status_check CHECK (
        status IN ('pending', 'extracting', 'extracted', 'summarizing', 'completed',
                   'failed', 'cancelled')
    );
"""


class EvidenceSummaryStoreUnavailable(RuntimeError):
    """Raised when the configured execution persistence is unavailable."""


class EvidenceSummaryStore:
    """Lazy Postgres store for one operator-authorized summary execution."""

    def __init__(self, database_url: str | None) -> None:
        self._database_url = database_url
        self._pool: asyncpg.Pool | None = None

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    async def _connection_pool(self) -> asyncpg.Pool:
        if not self._database_url:
            raise EvidenceSummaryStoreUnavailable("Summary persistence is not configured.")
        if self._pool is None:
            try:
                self._pool = await asyncpg.create_pool(
                    self._database_url,
                    min_size=1,
                    max_size=5,
                )
                async with self._pool.acquire() as connection:
                    await connection.execute(SCHEMA)
            except (asyncpg.PostgresError, OSError) as error:
                if self._pool is not None:
                    await self._pool.close()
                    self._pool = None
                raise EvidenceSummaryStoreUnavailable(
                    "Summary persistence is unavailable."
                ) from error
        return self._pool

    async def create_execution(
        self,
        workspace_id: UUID,
        run_id: UUID,
        urls: list[str],
    ) -> EvidenceSummaryExecution:
        pool = await self._connection_pool()
        execution_id = uuid4()
        async with pool.acquire() as connection, connection.transaction():
            row = await connection.fetchrow(
                """INSERT INTO evidence_summary_executions
                   (id, workspace_id, run_id, status)
                   VALUES ($1, $2, $3, 'extracting')
                   RETURNING id, workspace_id, run_id, route, status, created_at, updated_at""",
                execution_id,
                workspace_id,
                run_id,
            )
            for url in urls:
                await connection.execute(
                    """INSERT INTO evidence_summary_execution_sources
                       (execution_id, url, status) VALUES ($1, $2, 'pending')""",
                    execution_id,
                    url,
                )
        return EvidenceSummaryExecution(
            **dict(row),
            sources=[EvidenceSummaryExecutionSource(url=url) for url in urls],
        )

    async def mark_source_extracting(self, execution_id: UUID, url: str) -> None:
        await self._update_source(execution_id, url, "extracting")

    async def record_source_extracted(
        self,
        execution_id: UUID,
        url: str,
        content_hash: str,
        chunk_count: int,
    ) -> None:
        pool = await self._connection_pool()
        async with pool.acquire() as connection:
            await connection.execute(
                """UPDATE evidence_summary_execution_sources
                   SET status = 'extracted', content_hash = $3, chunk_count = $4,
                       failure_reason = NULL
                   WHERE execution_id = $1 AND url = $2""",
                execution_id,
                url,
                content_hash,
                chunk_count,
            )

    async def record_source_failure(self, execution_id: UUID, url: str, reason: str) -> None:
        pool = await self._connection_pool()
        async with pool.acquire() as connection:
            await connection.execute(
                """UPDATE evidence_summary_execution_sources
                   SET status = 'failed', failure_reason = $3
                   WHERE execution_id = $1 AND url = $2""",
                execution_id,
                url,
                reason,
            )

    async def set_execution_route(self, execution_id: UUID, route: str) -> None:
        await self._update_execution(execution_id, "awaiting_execution", route)

    async def mark_summarizing(self, execution_id: UUID) -> None:
        await self._update_execution(execution_id, "summarizing")

    async def record_source_summary(
        self,
        execution_id: UUID,
        url: str,
        summary: str,
        keywords: list[str],
    ) -> None:
        pool = await self._connection_pool()
        async with pool.acquire() as connection:
            await connection.execute(
                """UPDATE evidence_summary_execution_sources
                   SET status = 'completed', summary = $3, keywords = $4::jsonb
                   WHERE execution_id = $1 AND url = $2""",
                execution_id,
                url,
                summary,
                json.dumps(keywords),
            )

    async def complete_execution(self, execution_id: UUID) -> None:
        await self._update_execution(execution_id, "completed")

    async def fail_execution(self, execution_id: UUID) -> None:
        await self._update_execution(execution_id, "failed")

    async def get_execution(
        self,
        workspace_id: UUID,
        execution_id: UUID,
    ) -> EvidenceSummaryExecution | None:
        pool = await self._connection_pool()
        async with pool.acquire() as connection:
            row = await connection.fetchrow(
                """SELECT id, workspace_id, run_id, route, status, created_at, updated_at
                   FROM evidence_summary_executions
                   WHERE id = $1 AND workspace_id = $2""",
                execution_id,
                workspace_id,
            )
            if row is None:
                return None
            sources = await connection.fetch(
                """SELECT url, status, content_hash, chunk_count, summary, keywords,
                          failure_reason
                   FROM evidence_summary_execution_sources
                   WHERE execution_id = $1 ORDER BY url""",
                execution_id,
            )
        return EvidenceSummaryExecution(
            **dict(row),
            sources=[self._source_contract(source) for source in sources],
        )

    async def get_execution_for_worker(self, execution_id: UUID) -> EvidenceSummaryExecution | None:
        pool = await self._connection_pool()
        async with pool.acquire() as connection:
            workspace_id = await connection.fetchval(
                "SELECT workspace_id FROM evidence_summary_executions WHERE id = $1",
                execution_id,
            )
        return await self.get_execution(workspace_id, execution_id) if workspace_id else None

    async def _update_source(self, execution_id: UUID, url: str, status: str) -> None:
        pool = await self._connection_pool()
        async with pool.acquire() as connection:
            await connection.execute(
                """UPDATE evidence_summary_execution_sources SET status = $3
                   WHERE execution_id = $1 AND url = $2""",
                execution_id,
                url,
                status,
            )

    async def _update_execution(
        self,
        execution_id: UUID,
        status: str,
        route: str | None = None,
    ) -> None:
        pool = await self._connection_pool()
        async with pool.acquire() as connection:
            await connection.execute(
                """UPDATE evidence_summary_executions
                   SET status = $2, route = COALESCE($3, route), updated_at = now()
                   WHERE id = $1""",
                execution_id,
                status,
                route,
            )

    @staticmethod
    def _source_contract(source: asyncpg.Record) -> EvidenceSummaryExecutionSource:
        values = dict(source)
        if isinstance(values.get("keywords"), str):
            values["keywords"] = json.loads(values["keywords"])
        return EvidenceSummaryExecutionSource(**values)
