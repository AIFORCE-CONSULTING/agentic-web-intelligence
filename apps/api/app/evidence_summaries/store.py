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
    content_characters INTEGER,
    chunk_count INTEGER,
    chunking_policy_version TEXT,
    summary TEXT,
    keywords JSONB,
    evidence_sufficient BOOLEAN,
    artifact_id UUID,
    artifact_reused BOOLEAN NOT NULL DEFAULT FALSE,
    failure_reason TEXT,
    PRIMARY KEY (execution_id, url)
);
CREATE TABLE IF NOT EXISTS evidence_summary_artifacts (
    id UUID PRIMARY KEY,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    run_id UUID NOT NULL REFERENCES research_runs(id) ON DELETE CASCADE,
    source_url TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    content_characters INTEGER,
    chunk_count INTEGER,
    chunking_policy_version TEXT,
    summary TEXT NOT NULL,
    keywords JSONB NOT NULL,
    evidence_sufficient BOOLEAN NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (workspace_id, run_id, source_url, content_hash)
);
ALTER TABLE evidence_summary_artifacts ADD COLUMN IF NOT EXISTS content_characters INTEGER;
ALTER TABLE evidence_summary_artifacts ADD COLUMN IF NOT EXISTS chunk_count INTEGER;
ALTER TABLE evidence_summary_artifacts ADD COLUMN IF NOT EXISTS chunking_policy_version TEXT;
CREATE TABLE IF NOT EXISTS evidence_summary_execution_groups (
    execution_id UUID NOT NULL REFERENCES evidence_summary_executions(id) ON DELETE CASCADE,
    source_url TEXT NOT NULL,
    reduction_level INTEGER NOT NULL CHECK (reduction_level >= 1),
    group_index INTEGER NOT NULL CHECK (group_index >= 0),
    source_chunk_start INTEGER NOT NULL CHECK (source_chunk_start >= 0),
    source_chunk_end INTEGER NOT NULL CHECK (source_chunk_end > source_chunk_start),
    input_count INTEGER NOT NULL CHECK (input_count >= 1),
    summary TEXT NOT NULL,
    keywords JSONB NOT NULL,
    PRIMARY KEY (execution_id, source_url, reduction_level, group_index)
);
CREATE TABLE IF NOT EXISTS evidence_summary_execution_chunks (
    execution_id UUID NOT NULL REFERENCES evidence_summary_executions(id) ON DELETE CASCADE,
    source_url TEXT NOT NULL,
    chunk_index INTEGER NOT NULL CHECK (chunk_index >= 0),
    start_offset INTEGER NOT NULL CHECK (start_offset >= 0),
    end_offset INTEGER NOT NULL CHECK (end_offset > start_offset),
    summary TEXT NOT NULL,
    keywords JSONB NOT NULL,
    PRIMARY KEY (execution_id, source_url, chunk_index)
);
ALTER TABLE evidence_summary_executions ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ
    NOT NULL DEFAULT now();
ALTER TABLE evidence_summary_execution_sources ADD COLUMN IF NOT EXISTS summary TEXT;
ALTER TABLE evidence_summary_execution_sources ADD COLUMN IF NOT EXISTS keywords JSONB;
ALTER TABLE evidence_summary_execution_sources ADD COLUMN IF NOT EXISTS content_characters INTEGER;
ALTER TABLE evidence_summary_execution_sources ADD COLUMN IF NOT EXISTS chunking_policy_version TEXT;
ALTER TABLE evidence_summary_execution_sources ADD COLUMN IF NOT EXISTS evidence_sufficient BOOLEAN;
ALTER TABLE evidence_summary_execution_sources ADD COLUMN IF NOT EXISTS artifact_id UUID;
ALTER TABLE evidence_summary_execution_sources
    ADD COLUMN IF NOT EXISTS artifact_reused BOOLEAN NOT NULL DEFAULT FALSE;
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
        content_characters: int,
        chunk_count: int,
        chunking_policy_version: str,
    ) -> None:
        pool = await self._connection_pool()
        async with pool.acquire() as connection:
            await connection.execute(
                """UPDATE evidence_summary_execution_sources
                   SET status = 'extracted', content_hash = $3, content_characters = $4,
                       chunk_count = $5, chunking_policy_version = $6,
                       failure_reason = NULL
                   WHERE execution_id = $1 AND url = $2""",
                execution_id,
                url,
                content_hash,
                content_characters,
                chunk_count,
                chunking_policy_version,
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
        evidence_sufficient: bool,
    ) -> None:
        execution = await self.get_execution_for_worker(execution_id)
        if execution is None:
            raise EvidenceSummaryStoreUnavailable("Summary execution is unavailable.")
        source = next((item for item in execution.sources if item.url == url), None)
        if source is None or source.content_hash is None:
            raise EvidenceSummaryStoreUnavailable("Summary source evidence is unavailable.")
        pool = await self._connection_pool()
        artifact_id = uuid4()
        async with pool.acquire() as connection, connection.transaction():
            artifact = await connection.fetchrow(
                """INSERT INTO evidence_summary_artifacts
                   (id, workspace_id, run_id, source_url, content_hash, content_characters,
                    chunk_count, chunking_policy_version, summary, keywords, evidence_sufficient)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10::jsonb, $11)
                   ON CONFLICT (workspace_id, run_id, source_url, content_hash) DO UPDATE
                   SET summary = EXCLUDED.summary, keywords = EXCLUDED.keywords,
                       evidence_sufficient = EXCLUDED.evidence_sufficient
                   RETURNING id""",
                artifact_id,
                execution.workspace_id,
                execution.run_id,
                url,
                source.content_hash,
                source.content_characters,
                source.chunk_count,
                source.chunking_policy_version,
                summary,
                json.dumps(keywords),
                evidence_sufficient,
            )
            await connection.execute(
                """UPDATE evidence_summary_execution_sources
                   SET status = 'completed', summary = $3, keywords = $4::jsonb,
                       evidence_sufficient = $5, artifact_id = $6, artifact_reused = FALSE
                   WHERE execution_id = $1 AND url = $2""",
                execution_id,
                url,
                summary,
                json.dumps(keywords),
                evidence_sufficient,
                artifact["id"],
            )

    async def reuse_matching_artifact(
        self, execution_id: UUID, url: str, content_hash: str
    ) -> bool:
        """Link a matching durable per-source result without a retrieval or model call."""

        execution = await self.get_execution_for_worker(execution_id)
        if execution is None:
            raise EvidenceSummaryStoreUnavailable("Summary execution is unavailable.")
        pool = await self._connection_pool()
        async with pool.acquire() as connection, connection.transaction():
            artifact = await connection.fetchrow(
                """SELECT id, summary, keywords, evidence_sufficient
                   FROM evidence_summary_artifacts
                   WHERE workspace_id = $1 AND run_id = $2 AND source_url = $3
                     AND content_hash = $4""",
                execution.workspace_id,
                execution.run_id,
                url,
                content_hash,
            )
            if artifact is None:
                legacy = await connection.fetchrow(
                    """SELECT sources.summary, sources.keywords, sources.evidence_sufficient
                       FROM evidence_summary_execution_sources AS sources
                       JOIN evidence_summary_executions AS prior
                         ON prior.id = sources.execution_id
                       WHERE prior.workspace_id = $1 AND prior.run_id = $2
                         AND sources.url = $3 AND sources.content_hash = $4
                         AND sources.status = 'completed' AND sources.summary IS NOT NULL
                       ORDER BY prior.created_at DESC
                       LIMIT 1""",
                    execution.workspace_id,
                    execution.run_id,
                    url,
                    content_hash,
                )
                if legacy is None:
                    return False
                legacy_keywords = legacy["keywords"]
                if isinstance(legacy_keywords, str):
                    legacy_keywords = json.loads(legacy_keywords)
                await connection.execute(
                    """INSERT INTO evidence_summary_artifacts
                       (id, workspace_id, run_id, source_url, content_hash, summary, keywords,
                        evidence_sufficient)
                       VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8)
                       ON CONFLICT (workspace_id, run_id, source_url, content_hash) DO NOTHING""",
                    uuid4(),
                    execution.workspace_id,
                    execution.run_id,
                    url,
                    content_hash,
                    legacy["summary"],
                    json.dumps(legacy_keywords),
                    legacy["evidence_sufficient"]
                    if legacy["evidence_sufficient"] is not None
                    else True,
                )
                artifact = await connection.fetchrow(
                    """SELECT id, summary, keywords, evidence_sufficient
                       FROM evidence_summary_artifacts
                       WHERE workspace_id = $1 AND run_id = $2 AND source_url = $3
                         AND content_hash = $4""",
                    execution.workspace_id,
                    execution.run_id,
                    url,
                    content_hash,
                )
            artifact_keywords = artifact["keywords"]
            if isinstance(artifact_keywords, str):
                artifact_keywords = json.loads(artifact_keywords)
            await connection.execute(
                """UPDATE evidence_summary_execution_sources
                   SET status = 'completed', content_hash = $3, summary = $4,
                       keywords = $5::jsonb, evidence_sufficient = $6, artifact_id = $7,
                       artifact_reused = TRUE, failure_reason = NULL
                   WHERE execution_id = $1 AND url = $2""",
                execution_id,
                url,
                content_hash,
                artifact["summary"],
                json.dumps(artifact_keywords),
                artifact["evidence_sufficient"],
                artifact["id"],
            )
        return True

    async def record_chunk_summary(
        self,
        execution_id: UUID,
        source_url: str,
        chunk_index: int,
        start_offset: int,
        end_offset: int,
        summary: str,
        keywords: list[str],
    ) -> None:
        pool = await self._connection_pool()
        async with pool.acquire() as connection:
            await connection.execute(
                """INSERT INTO evidence_summary_execution_chunks
                   (execution_id, source_url, chunk_index, start_offset, end_offset,
                    summary, keywords)
                   VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb)
                   ON CONFLICT (execution_id, source_url, chunk_index) DO UPDATE
                   SET start_offset = EXCLUDED.start_offset, end_offset = EXCLUDED.end_offset,
                       summary = EXCLUDED.summary, keywords = EXCLUDED.keywords""",
                execution_id,
                source_url,
                chunk_index,
                start_offset,
                end_offset,
                summary,
                json.dumps(keywords),
            )

    async def record_consolidation_group(
        self,
        execution_id: UUID,
        source_url: str,
        reduction_level: int,
        group_index: int,
        source_chunk_start: int,
        source_chunk_end: int,
        input_count: int,
        summary: str,
        keywords: list[str],
    ) -> None:
        pool = await self._connection_pool()
        async with pool.acquire() as connection:
            await connection.execute(
                """INSERT INTO evidence_summary_execution_groups
                   (execution_id, source_url, reduction_level, group_index,
                    source_chunk_start, source_chunk_end, input_count, summary, keywords)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb)
                   ON CONFLICT (execution_id, source_url, reduction_level, group_index)
                   DO UPDATE SET source_chunk_start = EXCLUDED.source_chunk_start,
                     source_chunk_end = EXCLUDED.source_chunk_end, input_count = EXCLUDED.input_count,
                     summary = EXCLUDED.summary, keywords = EXCLUDED.keywords""",
                execution_id, source_url, reduction_level, group_index, source_chunk_start,
                source_chunk_end, input_count, summary, json.dumps(keywords),
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
                """SELECT url, status, content_hash, content_characters, chunk_count,
                          chunking_policy_version, summary, keywords,
                          evidence_sufficient, artifact_reused, failure_reason
                   FROM evidence_summary_execution_sources
                   WHERE execution_id = $1 ORDER BY url""",
                execution_id,
            )
        return EvidenceSummaryExecution(
            **dict(row),
            sources=[self._source_contract(source) for source in sources],
        )

    async def get_latest_execution_for_run(
        self,
        workspace_id: UUID,
        run_id: UUID,
    ) -> EvidenceSummaryExecution | None:
        """Return the most recent operator-authorized summary for one research run."""

        pool = await self._connection_pool()
        async with pool.acquire() as connection:
            execution_id = await connection.fetchval(
                """SELECT id FROM evidence_summary_executions
                   WHERE workspace_id = $1 AND run_id = $2
                   ORDER BY created_at DESC
                   LIMIT 1""",
                workspace_id,
                run_id,
            )
        return (
            await self.get_execution(workspace_id, execution_id)
            if execution_id is not None
            else None
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
