"""Canonical, workspace-scoped evidence-summary execution records."""

import json
from uuid import UUID, uuid4

import asyncpg

from app.evidence_summaries.contracts import (
    EvidenceSummaryExecution,
    EvidenceSummaryExecutionSource,
    EvidenceSummaryWorkSet,
    WorkspaceEvidenceSummaryArtifact,
)
from app.persistence import execute_schema_setup

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
    regeneration_attempt INTEGER NOT NULL DEFAULT 0,
    regeneration_requested BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS evidence_summary_work_sets (
    id UUID PRIMARY KEY,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    run_id UUID NOT NULL REFERENCES research_runs(id) ON DELETE CASCADE,
    status TEXT NOT NULL CHECK (status IN ('created', 'waiting', 'completed', 'failed')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ
);
CREATE TABLE IF NOT EXISTS evidence_summary_work_set_members (
    work_set_id UUID NOT NULL REFERENCES evidence_summary_work_sets(id) ON DELETE CASCADE,
    execution_id UUID NOT NULL REFERENCES evidence_summary_executions(id) ON DELETE CASCADE,
    PRIMARY KEY (work_set_id, execution_id)
);
CREATE INDEX IF NOT EXISTS evidence_summary_work_sets_run_idx
    ON evidence_summary_work_sets (workspace_id, run_id, created_at DESC);
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
    keyword_coverage JSONB,
    prompt_version TEXT,
    evidence_sufficient BOOLEAN,
    artifact_id UUID,
    artifact_reused BOOLEAN NOT NULL DEFAULT FALSE,
    failure_reason TEXT,
    failure_category TEXT,
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
    keyword_coverage JSONB,
    prompt_version TEXT,
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
CREATE TABLE IF NOT EXISTS evidence_summary_attempts (
    id UUID PRIMARY KEY,
    execution_id UUID NOT NULL REFERENCES evidence_summary_executions(id) ON DELETE CASCADE,
    regeneration_attempt INTEGER NOT NULL CHECK (regeneration_attempt >= 0),
    source_url TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    unit_kind TEXT NOT NULL CHECK (unit_kind IN ('chunk', 'consolidation_group', 'source_final')),
    unit_key TEXT NOT NULL,
    attempt_number INTEGER NOT NULL CHECK (attempt_number IN (1, 2)),
    state TEXT NOT NULL CHECK (state IN ('reserved', 'accepted', 'rejected', 'dependency_failed')),
    model_version TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    request_deadline TIMESTAMPTZ NOT NULL,
    validation_category TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,
    UNIQUE (execution_id, regeneration_attempt, source_url, content_hash, unit_kind, unit_key,
            attempt_number)
);
CREATE INDEX IF NOT EXISTS evidence_summary_attempts_execution_source_idx
    ON evidence_summary_attempts (execution_id, source_url, regeneration_attempt);
ALTER TABLE evidence_summary_executions ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ
    NOT NULL DEFAULT now();
ALTER TABLE evidence_summary_executions ADD COLUMN IF NOT EXISTS regeneration_attempt INTEGER
    NOT NULL DEFAULT 0;
ALTER TABLE evidence_summary_executions ADD COLUMN IF NOT EXISTS regeneration_requested BOOLEAN
    NOT NULL DEFAULT FALSE;
ALTER TABLE evidence_summary_execution_sources ADD COLUMN IF NOT EXISTS summary TEXT;
ALTER TABLE evidence_summary_execution_sources ADD COLUMN IF NOT EXISTS keywords JSONB;
ALTER TABLE evidence_summary_execution_sources ADD COLUMN IF NOT EXISTS keyword_coverage JSONB;
ALTER TABLE evidence_summary_execution_sources ADD COLUMN IF NOT EXISTS prompt_version TEXT;
ALTER TABLE evidence_summary_execution_sources ADD COLUMN IF NOT EXISTS content_characters INTEGER;
ALTER TABLE evidence_summary_execution_sources
    ADD COLUMN IF NOT EXISTS chunking_policy_version TEXT;
ALTER TABLE evidence_summary_execution_sources ADD COLUMN IF NOT EXISTS evidence_sufficient BOOLEAN;
ALTER TABLE evidence_summary_execution_sources ADD COLUMN IF NOT EXISTS artifact_id UUID;
ALTER TABLE evidence_summary_execution_sources
    ADD COLUMN IF NOT EXISTS artifact_reused BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE evidence_summary_execution_sources ADD COLUMN IF NOT EXISTS failure_reason TEXT;
ALTER TABLE evidence_summary_execution_sources ADD COLUMN IF NOT EXISTS failure_category TEXT;
ALTER TABLE evidence_summary_artifacts ADD COLUMN IF NOT EXISTS keyword_coverage JSONB;
ALTER TABLE evidence_summary_artifacts ADD COLUMN IF NOT EXISTS prompt_version TEXT;
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
                    await execute_schema_setup(connection, SCHEMA)
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
                   RETURNING id, workspace_id, run_id, route, status, regeneration_attempt,
                             regeneration_requested, created_at, updated_at""",
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

    async def create_work_set(self, workspace_id: UUID, run_id: UUID) -> EvidenceSummaryWorkSet:
        """Create the one coordination record for a graph-owned summary stage."""

        pool = await self._connection_pool()
        work_set_id = uuid4()
        async with pool.acquire() as connection:
            row = await connection.fetchrow(
                """INSERT INTO evidence_summary_work_sets (id, workspace_id, run_id, status)
                   VALUES ($1, $2, $3, 'created')
                   RETURNING id, workspace_id, run_id, status""",
                work_set_id, workspace_id, run_id,
            )
        return EvidenceSummaryWorkSet(**dict(row))

    async def attach_execution_to_work_set(self, work_set_id: UUID, execution_id: UUID) -> None:
        pool = await self._connection_pool()
        async with pool.acquire() as connection, connection.transaction():
            result = await connection.execute(
                """INSERT INTO evidence_summary_work_set_members (work_set_id, execution_id)
                   VALUES ($1, $2) ON CONFLICT DO NOTHING""",
                work_set_id, execution_id,
            )
            if result not in {"INSERT 0 1", "INSERT 0 0"}:
                raise EvidenceSummaryStoreUnavailable("Summary work-set membership conflicted.")
            await connection.execute(
                """UPDATE evidence_summary_work_sets SET status = 'waiting', updated_at = now()
                   WHERE id = $1 AND status = 'created'""",
                work_set_id,
            )

    async def refresh_work_set(self, work_set_id: UUID) -> EvidenceSummaryWorkSet | None:
        """Finalize only after every internal job is terminal."""

        pool = await self._connection_pool()
        async with pool.acquire() as connection, connection.transaction():
            row = await connection.fetchrow(
                """SELECT id, workspace_id, run_id, status
                   FROM evidence_summary_work_sets WHERE id = $1 FOR UPDATE""",
                work_set_id,
            )
            if row is None:
                return None
            statuses = await connection.fetch(
                """SELECT execution.status FROM evidence_summary_work_set_members AS member
                   JOIN evidence_summary_executions AS execution
                     ON execution.id = member.execution_id
                   WHERE member.work_set_id = $1""",
                work_set_id,
            )
            values = [item["status"] for item in statuses]
            terminal = values and all(
                value in {"completed", "failed", "cancelled"} for value in values
            )
            if terminal and row["status"] not in {"completed", "failed"}:
                outcome = "completed" if "completed" in values else "failed"
                row = await connection.fetchrow(
                    """UPDATE evidence_summary_work_sets
                       SET status = $2, updated_at = now(), completed_at = now()
                       WHERE id = $1
                       RETURNING id, workspace_id, run_id, status""",
                    work_set_id, outcome,
                )
            execution_ids = await connection.fetch(
                """SELECT execution_id FROM evidence_summary_work_set_members
                   WHERE work_set_id = $1 ORDER BY execution_id""",
                work_set_id,
            )
        return EvidenceSummaryWorkSet(
            **dict(row), execution_ids=[item["execution_id"] for item in execution_ids]
        )

    async def get_work_set(self, workspace_id: UUID, run_id: UUID) -> EvidenceSummaryWorkSet | None:
        pool = await self._connection_pool()
        async with pool.acquire() as connection:
            row = await connection.fetchrow(
                """SELECT id, workspace_id, run_id, status FROM evidence_summary_work_sets
                   WHERE workspace_id = $1 AND run_id = $2 ORDER BY created_at DESC LIMIT 1""",
                workspace_id, run_id,
            )
            if row is None:
                return None
            execution_ids = await connection.fetch(
                """SELECT execution_id FROM evidence_summary_work_set_members
                   WHERE work_set_id = $1 ORDER BY execution_id""",
                row["id"],
            )
        return EvidenceSummaryWorkSet(
            **dict(row), execution_ids=[item["execution_id"] for item in execution_ids]
        )

    async def refresh_work_set_for_execution(
        self, execution_id: UUID
    ) -> EvidenceSummaryWorkSet | None:
        pool = await self._connection_pool()
        async with pool.acquire() as connection:
            work_set_id = await connection.fetchval(
                """SELECT work_set_id FROM evidence_summary_work_set_members
                   WHERE execution_id = $1""",
                execution_id,
            )
        return await self.refresh_work_set(work_set_id) if work_set_id else None

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
                       failure_reason = NULL, failure_category = NULL
                   WHERE execution_id = $1 AND url = $2""",
                execution_id,
                url,
                content_hash,
                content_characters,
                chunk_count,
                chunking_policy_version,
            )

    async def record_source_failure(
        self,
        execution_id: UUID,
        url: str,
        reason: str,
        category: str | None = None,
    ) -> None:
        pool = await self._connection_pool()
        async with pool.acquire() as connection:
            await connection.execute(
                """UPDATE evidence_summary_execution_sources
                   SET status = 'failed', failure_reason = $3, failure_category = $4
                   WHERE execution_id = $1 AND url = $2""",
                execution_id,
                url,
                reason,
                category,
            )

    async def set_execution_route(self, execution_id: UUID, route: str) -> None:
        await self._update_execution(execution_id, "awaiting_execution", route)

    async def mark_summarizing(self, execution_id: UUID) -> None:
        await self._update_execution(execution_id, "summarizing")

    async def begin_regeneration(
        self,
        execution_id: UUID,
        urls: list[str],
    ) -> None:
        """Reset only derived records; extracted evidence is deliberately retained."""

        pool = await self._connection_pool()
        async with pool.acquire() as connection, connection.transaction():
            await connection.execute(
                """DELETE FROM evidence_summary_execution_chunks
                   WHERE execution_id = $1 AND source_url = ANY($2::text[])""",
                execution_id,
                urls,
            )
            await connection.execute(
                """UPDATE evidence_summary_executions
                   SET status = 'extracting', route = 'undetermined',
                       regeneration_attempt = regeneration_attempt + 1,
                       regeneration_requested = TRUE, updated_at = now()
                   WHERE id = $1""",
                execution_id,
            )
            await connection.execute(
                """DELETE FROM evidence_summary_execution_groups
                   WHERE execution_id = $1 AND source_url = ANY($2::text[])""",
                execution_id,
                urls,
            )
            await connection.execute(
                """UPDATE evidence_summary_execution_sources
                   SET status = 'extracted', summary = NULL, keywords = NULL,
                       keyword_coverage = NULL, prompt_version = NULL,
                       evidence_sufficient = NULL, artifact_id = NULL, artifact_reused = FALSE,
                       failure_reason = NULL, failure_category = NULL
                   WHERE execution_id = $1 AND url = ANY($2::text[])""",
                execution_id,
                urls,
            )

    async def reserve_model_attempt(
        self,
        execution_id: UUID,
        source_url: str,
        content_hash: str,
        unit_kind: str,
        unit_key: str,
        regeneration_attempt: int,
        attempt_number: int,
        model_version: str,
        prompt_version: str,
        deadline_seconds: int,
    ) -> str:
        """Claim a single call slot before sending trusted evidence to the provider.

        A duplicate worker never receives another slot. A reservation that outlives its deadline is
        converted to a dependency failure rather than retried invisibly.
        """

        pool = await self._connection_pool()
        async with pool.acquire() as connection, connection.transaction():
            existing = await connection.fetchrow(
                """SELECT state, request_deadline < now() AS stale
                   FROM evidence_summary_attempts
                   WHERE execution_id = $1 AND regeneration_attempt = $2 AND source_url = $3
                     AND content_hash = $4 AND unit_kind = $5 AND unit_key = $6
                     AND attempt_number = $7
                   FOR UPDATE""",
                execution_id, regeneration_attempt, source_url, content_hash, unit_kind,
                unit_key, attempt_number,
            )
            if existing is not None:
                if existing["state"] == "reserved" and existing["stale"]:
                    await connection.execute(
                        """UPDATE evidence_summary_attempts
                           SET state = 'dependency_failed', validation_category =
                               'stale_reservation', completed_at = now()
                           WHERE execution_id = $1 AND regeneration_attempt = $2
                             AND source_url = $3 AND content_hash = $4 AND unit_kind = $5
                             AND unit_key = $6 AND attempt_number = $7""",
                        execution_id, regeneration_attempt, source_url, content_hash, unit_kind,
                        unit_key, attempt_number,
                    )
                    return "stale"
                return "existing"
            await connection.execute(
                """INSERT INTO evidence_summary_attempts
                   (id, execution_id, regeneration_attempt, source_url, content_hash, unit_kind,
                    unit_key, attempt_number, state, model_version, prompt_version,
                    request_deadline)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'reserved', $9, $10,
                           now() + ($11 * interval '1 second'))""",
                uuid4(), execution_id, regeneration_attempt, source_url, content_hash,
                unit_kind, unit_key, attempt_number, model_version, prompt_version,
                deadline_seconds,
            )
        return "reserved"

    async def accept_model_attempt(
        self, execution_id: UUID, source_url: str, content_hash: str, unit_kind: str,
        unit_key: str, regeneration_attempt: int, attempt_number: int,
    ) -> None:
        await self._complete_model_attempt(
            execution_id, source_url, content_hash, unit_kind, unit_key, regeneration_attempt,
            attempt_number, "accepted", None,
        )

    async def reject_model_attempt(
        self, execution_id: UUID, source_url: str, content_hash: str, unit_kind: str,
        unit_key: str, regeneration_attempt: int, attempt_number: int, category: str,
    ) -> None:
        await self._complete_model_attempt(
            execution_id, source_url, content_hash, unit_kind, unit_key, regeneration_attempt,
            attempt_number, "rejected", category,
        )

    async def mark_model_attempt_dependency_failed(
        self, execution_id: UUID, source_url: str, content_hash: str, unit_kind: str,
        unit_key: str, regeneration_attempt: int, attempt_number: int, category: str,
    ) -> None:
        await self._complete_model_attempt(
            execution_id, source_url, content_hash, unit_kind, unit_key, regeneration_attempt,
            attempt_number, "dependency_failed", category,
        )

    async def _complete_model_attempt(
        self, execution_id: UUID, source_url: str, content_hash: str, unit_kind: str,
        unit_key: str, regeneration_attempt: int, attempt_number: int, state: str,
        category: str | None,
    ) -> None:
        pool = await self._connection_pool()
        async with pool.acquire() as connection:
            result = await connection.execute(
                """UPDATE evidence_summary_attempts
                   SET state = $8, validation_category = $9, completed_at = now()
                   WHERE execution_id = $1 AND regeneration_attempt = $2 AND source_url = $3
                     AND content_hash = $4 AND unit_kind = $5 AND unit_key = $6
                     AND attempt_number = $7 AND state = 'reserved'""",
                execution_id, regeneration_attempt, source_url, content_hash, unit_kind,
                unit_key, attempt_number, state, category,
            )
        if result != "UPDATE 1":
            raise EvidenceSummaryStoreUnavailable("Summary attempt state conflicted.")

    async def record_source_summary(
        self,
        execution_id: UUID,
        url: str,
        summary: str,
        keywords: list[str],
        prompt_version: str,
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
                    chunk_count, chunking_policy_version, summary, keywords, keyword_coverage,
                    prompt_version, evidence_sufficient)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10::jsonb, $11::jsonb, $12, $13)
                   ON CONFLICT (workspace_id, run_id, source_url, content_hash) DO UPDATE
                   SET summary = EXCLUDED.summary, keywords = EXCLUDED.keywords,
                       keyword_coverage = NULL,
                       prompt_version = EXCLUDED.prompt_version,
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
                None,
                prompt_version,
                evidence_sufficient,
            )
            await connection.execute(
                """UPDATE evidence_summary_execution_sources
                   SET status = 'completed', summary = $3, keywords = $4::jsonb,
                       keyword_coverage = NULL, prompt_version = $5,
                       evidence_sufficient = $6, artifact_id = $7, artifact_reused = FALSE,
                       failure_reason = NULL, failure_category = NULL
                   WHERE execution_id = $1 AND url = $2""",
                execution_id,
                url,
                summary,
                json.dumps(keywords),
                prompt_version,
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
                """SELECT id, summary, keywords, keyword_coverage, prompt_version,
                          evidence_sufficient
                   FROM evidence_summary_artifacts
                   WHERE workspace_id = $1 AND source_url = $2 AND content_hash = $3
                   ORDER BY created_at DESC LIMIT 1""",
                execution.workspace_id,
                url,
                content_hash,
            )
            if artifact is None:
                legacy = await connection.fetchrow(
                    """SELECT sources.summary, sources.keywords, sources.keyword_coverage,
                              sources.prompt_version, sources.evidence_sufficient
                       FROM evidence_summary_execution_sources AS sources
                       JOIN evidence_summary_executions AS prior
                         ON prior.id = sources.execution_id
                       WHERE prior.workspace_id = $1 AND sources.url = $2
                         AND sources.content_hash = $3
                         AND sources.status = 'completed' AND sources.summary IS NOT NULL
                       ORDER BY prior.created_at DESC
                       LIMIT 1""",
                    execution.workspace_id,
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
                        keyword_coverage, prompt_version, evidence_sufficient)
                       VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8::jsonb, $9, $10)
                       ON CONFLICT (workspace_id, run_id, source_url, content_hash) DO NOTHING""",
                    uuid4(),
                    execution.workspace_id,
                    execution.run_id,
                    url,
                    content_hash,
                    legacy["summary"],
                    json.dumps(legacy_keywords),
                    json.dumps(legacy["keyword_coverage"]),
                    legacy["prompt_version"],
                    legacy["evidence_sufficient"]
                    if legacy["evidence_sufficient"] is not None
                    else True,
                )
                artifact = await connection.fetchrow(
                    """SELECT id, summary, keywords, keyword_coverage, prompt_version,
                              evidence_sufficient
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
            artifact_coverage = artifact["keyword_coverage"]
            if isinstance(artifact_coverage, str):
                artifact_coverage = json.loads(artifact_coverage)
            await connection.execute(
                """UPDATE evidence_summary_execution_sources
                   SET status = 'completed', content_hash = $3, summary = $4,
                       keywords = $5::jsonb, keyword_coverage = $6::jsonb,
                       prompt_version = $7, evidence_sufficient = $8, artifact_id = $9,
                       artifact_reused = TRUE, failure_reason = NULL
                   WHERE execution_id = $1 AND url = $2""",
                execution_id,
                url,
                content_hash,
                artifact["summary"],
                json.dumps(artifact_keywords),
                json.dumps(artifact_coverage),
                artifact["prompt_version"],
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
                     source_chunk_end = EXCLUDED.source_chunk_end,
                     input_count = EXCLUDED.input_count,
                     summary = EXCLUDED.summary, keywords = EXCLUDED.keywords""",
                execution_id, source_url, reduction_level, group_index, source_chunk_start,
                source_chunk_end, input_count, summary, json.dumps(keywords),
            )

    async def complete_execution(self, execution_id: UUID) -> None:
        pool = await self._connection_pool()
        async with pool.acquire() as connection:
            await connection.execute(
                """UPDATE evidence_summary_executions
                   SET status = CASE WHEN EXISTS (
                           SELECT 1 FROM evidence_summary_execution_sources
                           WHERE execution_id = $1 AND status = 'completed'
                             AND evidence_sufficient IS TRUE
                       ) THEN 'completed' ELSE 'failed' END,
                       regeneration_requested = FALSE, updated_at = now()
                   WHERE id = $1""",
                execution_id,
            )

    async def has_evidence_sufficient_result(self, execution_id: UUID) -> bool:
        """Verify a durable continuation against the execution's stored business outcome."""

        pool = await self._connection_pool()
        async with pool.acquire() as connection:
            return bool(
                await connection.fetchval(
                    """SELECT EXISTS (
                           SELECT 1 FROM evidence_summary_execution_sources
                           WHERE execution_id = $1 AND status = 'completed'
                             AND evidence_sufficient IS TRUE
                       )""",
                    execution_id,
                )
            )

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
                """SELECT id, workspace_id, run_id, route, status, regeneration_attempt,
                          regeneration_requested, created_at, updated_at
                   FROM evidence_summary_executions
                   WHERE id = $1 AND workspace_id = $2""",
                execution_id,
                workspace_id,
            )
            if row is None:
                return None
            sources = await connection.fetch(
                """SELECT sources.url, sources.status, sources.content_hash,
                          sources.content_characters, sources.chunk_count,
                          chunking_policy_version, summary, keywords,
                          keyword_coverage, prompt_version,
                          evidence_sufficient, artifact_reused, failure_reason, failure_category,
                          COALESCE(attempts.summary_attempt_count, 0) AS summary_attempt_count,
                          attempts.model_version
                   FROM evidence_summary_execution_sources AS sources
                   LEFT JOIN LATERAL (
                       SELECT COUNT(*)::integer AS summary_attempt_count,
                              (
                                  SELECT model_version
                                  FROM evidence_summary_attempts AS latest
                                  WHERE latest.execution_id = sources.execution_id
                                    AND latest.source_url = sources.url
                                    AND latest.regeneration_attempt = $2
                                  ORDER BY latest.created_at DESC LIMIT 1
                              ) AS model_version
                       FROM evidence_summary_attempts
                       WHERE execution_id = sources.execution_id AND source_url = sources.url
                         AND regeneration_attempt = $2
                   ) AS attempts ON TRUE
                   WHERE sources.execution_id = $1 ORDER BY sources.url""",
                execution_id,
                dict(row).get("regeneration_attempt", 0),
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

    async def list_workspace_artifacts(
        self, workspace_id: UUID, limit: int = 500
    ) -> list[WorkspaceEvidenceSummaryArtifact]:
        """Return the newest usable summary once for each workspace URL."""

        pool = await self._connection_pool()
        async with pool.acquire() as connection:
            rows = await connection.fetch(
                """SELECT DISTINCT ON (artifacts.source_url)
                          artifacts.run_id, artifacts.source_url AS url,
                          COALESCE(source.title, artifacts.source_url) AS title,
                          artifacts.chunk_count, artifacts.summary, artifacts.keywords,
                          artifacts.keyword_coverage, artifacts.prompt_version,
                          artifacts.evidence_sufficient
                   FROM evidence_summary_artifacts AS artifacts
                   LEFT JOIN LATERAL (
                       SELECT title FROM research_sources
                       WHERE run_id = artifacts.run_id AND url = artifacts.source_url
                       ORDER BY rank
                       LIMIT 1
                   ) AS source ON TRUE
                   WHERE artifacts.workspace_id = $1
                   ORDER BY artifacts.source_url, artifacts.created_at DESC
                   LIMIT $2""",
                workspace_id,
                limit,
            )
        return [self._artifact_contract(row) for row in rows]

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
        if isinstance(values.get("keyword_coverage"), str):
            values["keyword_coverage"] = json.loads(values["keyword_coverage"])
        return EvidenceSummaryExecutionSource(**values)

    @staticmethod
    def _artifact_contract(artifact: asyncpg.Record) -> WorkspaceEvidenceSummaryArtifact:
        values = dict(artifact)
        if isinstance(values.get("keywords"), str):
            values["keywords"] = json.loads(values["keywords"])
        if isinstance(values.get("keyword_coverage"), str):
            values["keyword_coverage"] = json.loads(values["keyword_coverage"])
        return WorkspaceEvidenceSummaryArtifact(**values)
