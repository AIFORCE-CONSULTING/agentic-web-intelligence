"""Postgres-backed, append-only records for governed research runs."""

import json
import re
from collections.abc import Callable
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
    workspace_id UUID,
    question TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('searching', 'ready', 'failed')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS research_target_keys (
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    normalized_question TEXT NOT NULL,
    run_id UUID NOT NULL UNIQUE REFERENCES research_runs(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (workspace_id, normalized_question)
);
CREATE TABLE IF NOT EXISTS research_sources (
    id UUID PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES research_runs(id) ON DELETE CASCADE,
    rank INTEGER NOT NULL CHECK (rank > 0),
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    snippet TEXT NOT NULL DEFAULT '',
    engine TEXT,
    preflight_status TEXT NOT NULL DEFAULT 'pending',
    preflight_reason TEXT,
    preflight_checked_at TIMESTAMPTZ,
    preflight_content_type TEXT,
    preflight_content_hash TEXT,
    preflight_trust_disposition TEXT,
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
    workspace_id UUID,
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
ALTER TABLE research_runs ADD COLUMN IF NOT EXISTS workspace_id UUID;
ALTER TABLE mcp_tool_audit_events ADD COLUMN IF NOT EXISTS workspace_id UUID;
ALTER TABLE research_sources
    ADD COLUMN IF NOT EXISTS preflight_status TEXT NOT NULL DEFAULT 'pending';
ALTER TABLE research_sources ADD COLUMN IF NOT EXISTS preflight_reason TEXT;
ALTER TABLE research_sources ADD COLUMN IF NOT EXISTS preflight_checked_at TIMESTAMPTZ;
ALTER TABLE research_sources ADD COLUMN IF NOT EXISTS preflight_content_type TEXT;
ALTER TABLE research_sources ADD COLUMN IF NOT EXISTS preflight_content_hash TEXT;
ALTER TABLE research_sources ADD COLUMN IF NOT EXISTS preflight_trust_disposition TEXT;
ALTER TABLE research_runs DROP CONSTRAINT IF EXISTS research_runs_status_check;
ALTER TABLE research_runs ADD CONSTRAINT research_runs_status_check CHECK (
    status IN ('searching', 'preflighting', 'ready', 'failed')
);
CREATE INDEX IF NOT EXISTS research_runs_workspace_updated_at_idx
    ON research_runs(workspace_id, updated_at DESC);
INSERT INTO research_target_keys (workspace_id, normalized_question, run_id)
SELECT DISTINCT ON (workspace_id, lower(regexp_replace(btrim(question), '\\s+', ' ', 'g')))
       workspace_id, lower(regexp_replace(btrim(question), '\\s+', ' ', 'g')), id
FROM research_runs
WHERE workspace_id IS NOT NULL
ORDER BY workspace_id, lower(regexp_replace(btrim(question), '\\s+', ' ', 'g')),
         updated_at DESC
ON CONFLICT (workspace_id, normalized_question) DO NOTHING;
CREATE INDEX IF NOT EXISTS mcp_tool_audit_events_workspace_occurred_at_idx
    ON mcp_tool_audit_events(workspace_id, occurred_at DESC);
"""


class ResearchStore:
    """Lazy Postgres store so API startup does not race optional Compose services."""

    def __init__(
        self,
        database_url: str | None,
        redact: Callable[[object], object] | None = None,
    ) -> None:
        self._database_url = database_url
        self._pool: asyncpg.Pool | None = None
        self._redact = redact or (lambda value: value)

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

    async def get_or_create_run(
        self, workspace_id: UUID, question: str
    ) -> tuple[ResearchRun, bool]:
        """Return the one canonical workspace target for a normalized question."""

        run_id = uuid4()
        normalized_question = self._normalize_question(question)
        pool = await self._connection_pool()
        async with pool.acquire() as connection, connection.transaction():
            await connection.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended($1, 0))",
                f"{workspace_id}:{normalized_question}",
            )
            existing = await connection.fetchrow(
                """SELECT runs.id, runs.question, runs.status, runs.created_at, runs.updated_at
                   FROM research_target_keys AS target
                   JOIN research_runs AS runs ON runs.id = target.run_id
                   WHERE target.workspace_id = $1 AND target.normalized_question = $2""",
                workspace_id,
                normalized_question,
            )
            if existing is not None:
                return ResearchRun(**dict(existing)), False
            row = await connection.fetchrow(
                """INSERT INTO research_runs (id, workspace_id, question, status)
                   VALUES ($1, $2, $3, 'searching')
                   RETURNING id, question, status, created_at, updated_at""",
                run_id,
                workspace_id,
                question,
            )
            await connection.execute(
                """INSERT INTO research_target_keys (workspace_id, normalized_question, run_id)
                   VALUES ($1, $2, $3)""",
                workspace_id,
                normalized_question,
                run_id,
            )
            await self._append_audit(
                connection, run_id, "research.run.created", {"question": question}
            )
        return ResearchRun(**dict(row)), True

    async def healthcheck(self) -> None:
        """Confirm that the configured persistence store accepts a trivial query."""

        pool = await self._connection_pool()
        async with pool.acquire() as connection:
            await connection.fetchval("SELECT 1")

    async def record_mcp_tool_event(
        self,
        workspace_id: UUID,
        request_id: str | None,
        tool_name: str,
        outcome: str,
        details: dict[str, object],
    ) -> None:
        """Append one direct MCP execution outcome without creating a research run."""

        pool = await self._connection_pool()
        async with pool.acquire() as connection:
            await connection.execute(
                """INSERT INTO mcp_tool_audit_events
                   (id, workspace_id, request_id, tool_name, outcome, details)
                   VALUES ($1, $2, $3, $4, $5, $6::jsonb)""",
                uuid4(),
                workspace_id,
                request_id,
                tool_name,
                outcome,
                json.dumps(self._redact(details)),
            )

    async def list_mcp_tool_events(
        self, workspace_id: UUID, limit: int
    ) -> list[McpToolAuditEvent]:
        """Return recent direct MCP outcomes without retaining retrieved page content."""

        pool = await self._connection_pool()
        async with pool.acquire() as connection:
            rows = await connection.fetch(
                """SELECT id, request_id, tool_name, outcome, occurred_at, details
                   FROM mcp_tool_audit_events WHERE workspace_id = $1
                   ORDER BY occurred_at DESC LIMIT $2""",
                workspace_id,
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
            workspace_id = await connection.fetchval(
                "SELECT workspace_id FROM research_runs WHERE id = $1", run_id
            )
            if workspace_id is None:
                raise KeyError(run_id)
            reused_count = 0
            for source in sources:
                known = await connection.fetchrow(
                    """SELECT sources.preflight_status, sources.preflight_reason,
                              sources.preflight_checked_at, sources.preflight_content_type,
                              sources.preflight_content_hash, sources.preflight_trust_disposition
                       FROM research_sources AS sources
                       JOIN research_runs AS owner ON owner.id = sources.run_id
                       WHERE owner.workspace_id = $1 AND sources.url = $2
                         AND sources.run_id <> $3
                         AND sources.preflight_status NOT IN ('pending', 'checking')
                       ORDER BY sources.preflight_checked_at DESC NULLS LAST, owner.updated_at DESC
                       LIMIT 1""",
                    workspace_id,
                    source.url,
                    run_id,
                )
                if known is not None:
                    reused_count += 1
                await connection.execute(
                    """INSERT INTO research_sources
                       (id, run_id, rank, title, url, snippet, engine, preflight_status,
                        preflight_reason, preflight_checked_at, preflight_content_type,
                        preflight_content_hash, preflight_trust_disposition)
                       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)""",
                    uuid4(),
                    run_id,
                    source.rank,
                    source.title,
                    source.url,
                    source.snippet,
                    source.engine,
                    known["preflight_status"] if known else "pending",
                    known["preflight_reason"] if known else None,
                    known["preflight_checked_at"] if known else None,
                    known["preflight_content_type"] if known else None,
                    known["preflight_content_hash"] if known else None,
                    known["preflight_trust_disposition"] if known else None,
                )
            await self._append_audit(
                connection,
                run_id,
                "research.search.completed",
                {"source_count": len(sources), "reused_source_count": reused_count},
            )
            await connection.execute(
                """UPDATE research_runs SET status = 'preflighting', updated_at = now()
                   WHERE id = $1""",
                run_id,
            )

    async def mark_candidate_checking(self, run_id: UUID, url: str) -> None:
        pool = await self._connection_pool()
        async with pool.acquire() as connection:
            await connection.execute(
                """UPDATE research_sources
                   SET preflight_status = 'checking', preflight_reason = NULL
                   WHERE run_id = $1 AND url = $2 AND preflight_status = 'pending'""",
                run_id,
                url,
            )

    async def record_candidate_preflight(
        self,
        run_id: UUID,
        url: str,
        status: str,
        reason: str | None = None,
        content_type: str | None = None,
        content_hash: str | None = None,
        trust_disposition: str | None = None,
    ) -> None:
        """Persist one candidate result even when no evidence can be retained."""

        pool = await self._connection_pool()
        async with pool.acquire() as connection, connection.transaction():
            await connection.execute(
                """UPDATE research_sources
                   SET preflight_status = $3, preflight_reason = $4, preflight_checked_at = now(),
                       preflight_content_type = $5, preflight_content_hash = $6,
                       preflight_trust_disposition = $7
                   WHERE run_id = $1 AND url = $2""",
                run_id, url, status, reason, content_type, content_hash, trust_disposition,
            )
            await self._append_audit(
                connection,
                run_id,
                "research.candidate.preflight.completed",
                {
                    "url": url,
                    "status": status,
                    "reason": reason,
                    "content_hash": content_hash,
                    "trust_disposition": trust_disposition,
                },
            )
            await connection.execute(
                "UPDATE research_runs SET updated_at = now() WHERE id = $1", run_id
            )

    async def complete_candidate_preflight(self, run_id: UUID) -> None:
        pool = await self._connection_pool()
        async with pool.acquire() as connection, connection.transaction():
            counts = await connection.fetchrow(
                """SELECT COUNT(*) FILTER (WHERE preflight_status = 'ready_to_extract')::integer
                              AS ready,
                          COUNT(*) FILTER (WHERE preflight_status = 'review_required')::integer
                              AS review,
                          COUNT(*) FILTER (WHERE preflight_status = 'blocked')::integer AS blocked,
                          COUNT(*) FILTER (WHERE preflight_status = 'unreachable')::integer
                              AS unreachable
                   FROM research_sources WHERE run_id = $1""",
                run_id,
            )
            await self._append_audit(
                connection, run_id, "research.candidate.preflight.finished", dict(counts)
            )
            await connection.execute(
                "UPDATE research_runs SET status = 'ready', updated_at = now() WHERE id = $1",
                run_id,
            )

    async def fail_candidate_preflight(self, run_id: UUID, reason: str) -> None:
        pool = await self._connection_pool()
        async with pool.acquire() as connection, connection.transaction():
            await self._append_audit(
                connection, run_id, "research.candidate.preflight.failed", {"reason": reason}
            )
            await connection.execute(
                "UPDATE research_runs SET status = 'failed', updated_at = now() WHERE id = $1",
                run_id,
            )

    async def workspace_id_for_run(self, run_id: UUID) -> UUID | None:
        pool = await self._connection_pool()
        async with pool.acquire() as connection:
            return await connection.fetchval(
                "SELECT workspace_id FROM research_runs WHERE id = $1", run_id
            )

    async def save_evidence(self, run_id: UUID, evidence: Evidence) -> None:
        pool = await self._connection_pool()
        async with pool.acquire() as connection, connection.transaction():
            exists = await connection.fetchval("SELECT 1 FROM research_runs WHERE id = $1", run_id)
            if not exists:
                raise KeyError(run_id)
            known = await connection.fetchval(
                """SELECT 1 FROM research_evidence AS existing
                   JOIN research_runs AS owner ON owner.id = existing.run_id
                   JOIN research_runs AS current_run ON current_run.id = $1
                   WHERE owner.workspace_id = current_run.workspace_id
                     AND existing.url = $2 AND existing.content_hash = $3
                   LIMIT 1""",
                run_id,
                evidence.url,
                evidence.content_hash,
            )
            if known:
                await self._append_audit(
                    connection,
                    run_id,
                    "research.evidence.reused",
                    {"url": evidence.url, "content_hash": evidence.content_hash},
                )
                return
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

    async def run_exists(self, workspace_id: UUID, run_id: UUID) -> bool:
        """Confirm a run exists before invoking an external retrieval action for it."""

        pool = await self._connection_pool()
        async with pool.acquire() as connection:
            return bool(
                await connection.fetchval(
                    "SELECT 1 FROM research_runs WHERE id = $1 AND workspace_id = $2",
                    run_id,
                    workspace_id,
                )
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

    async def record_source_reused(self, run_id: UUID, url: str) -> None:
        """Record that an operator-selected source reused its latest governed evidence."""

        pool = await self._connection_pool()
        async with pool.acquire() as connection, connection.transaction():
            await self._append_audit(
                connection, run_id, "research.evidence.reused", {"url": url}
            )
            await connection.execute(
                "UPDATE research_runs SET updated_at = now() WHERE id = $1", run_id
            )

    async def record_automatic_summary_requested(self, run_id: UUID, urls: list[str]) -> None:
        """Record platform-selected derived work without implying an operator extraction action."""

        pool = await self._connection_pool()
        async with pool.acquire() as connection, connection.transaction():
            await self._append_audit(
                connection,
                run_id,
                "research.evidence_summary.automatic_requested",
                {"source_count": len(urls), "urls": urls},
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

    async def record_summary_regeneration_requested(self, run_id: UUID, urls: list[str]) -> None:
        """Record an explicit operator decision before derived evidence is overwritten."""

        pool = await self._connection_pool()
        async with pool.acquire() as connection, connection.transaction():
            await self._append_audit(
                connection,
                run_id,
                "research.evidence_summary.regeneration_requested",
                {"selected_count": len(urls), "urls": urls},
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

    async def get_run(self, workspace_id: UUID, run_id: UUID) -> ResearchRun | None:
        pool = await self._connection_pool()
        async with pool.acquire() as connection:
            run = await connection.fetchrow(
                "SELECT * FROM research_runs WHERE id = $1 AND workspace_id = $2",
                run_id,
                workspace_id,
            )
            if run is None:
                return None
            sources = await connection.fetch(
                """SELECT rank, title, url, snippet, engine, preflight_status, preflight_reason,
                          preflight_checked_at, preflight_content_type, preflight_content_hash,
                          preflight_trust_disposition FROM research_sources
                   WHERE run_id = $1 ORDER BY rank""",
                run_id,
            )
            evidence = await connection.fetch(
                """SELECT url, retrieved_at, content_type, text, content_hash, extraction_method
                   FROM (
                       SELECT DISTINCT ON (url)
                           evidence.url, evidence.retrieved_at, evidence.content_type,
                           evidence.text,
                           evidence.content_hash, evidence.extraction_method
                       FROM research_evidence AS evidence
                       JOIN research_runs AS owner ON owner.id = evidence.run_id
                       JOIN research_sources AS candidate ON candidate.url = evidence.url
                       WHERE candidate.run_id = $1 AND owner.workspace_id = $2
                       ORDER BY evidence.url, evidence.retrieved_at DESC
                   ) AS latest_evidence
                   ORDER BY retrieved_at""",
                run_id,
                workspace_id,
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

    async def list_runs(self, workspace_id: UUID, limit: int) -> list[ResearchRunSummary]:
        """Return a bounded run library without loading evidence text into the list view."""

        pool = await self._connection_pool()
        async with pool.acquire() as connection:
            rows = await connection.fetch(
                """SELECT runs.id, runs.question, runs.status, runs.created_at, runs.updated_at,
                          COUNT(DISTINCT sources.id)::integer AS source_count,
                          COUNT(DISTINCT evidence.id)::integer AS evidence_count
                   FROM research_runs AS runs
                   LEFT JOIN research_sources AS sources ON sources.run_id = runs.id
                   LEFT JOIN research_sources AS evidence_source ON evidence_source.run_id = runs.id
                   LEFT JOIN research_evidence AS evidence ON evidence.url = evidence_source.url
                   LEFT JOIN research_runs AS evidence_owner ON evidence_owner.id = evidence.run_id
                   WHERE runs.workspace_id = $1
                     AND (evidence_owner.workspace_id = $1 OR evidence_owner.workspace_id IS NULL)
                   GROUP BY runs.id
                   ORDER BY runs.updated_at DESC
                   LIMIT $2""",
                workspace_id,
                limit,
            )
        return [ResearchRunSummary(**dict(row)) for row in rows]

    async def _append_audit(
        self,
        connection: asyncpg.Connection,
        run_id: UUID,
        event_type: str,
        details: dict[str, object],
    ) -> None:
        await connection.execute(
            """INSERT INTO research_audit_events (id, run_id, event_type, details)
               VALUES ($1, $2, $3, $4::jsonb)""",
            uuid4(),
            run_id,
            event_type,
            json.dumps(self._redact(details)),
        )

    @staticmethod
    def _details(value: object) -> dict[str, object]:
        return json.loads(value) if isinstance(value, str) else dict(value)

    @staticmethod
    def _normalize_question(question: str) -> str:
        return re.sub(r"\s+", " ", question.strip()).casefold()
