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
    status TEXT NOT NULL DEFAULT 'planning',
    status_version INTEGER NOT NULL DEFAULT 0 CHECK (status_version >= 0),
    failed_stage TEXT,
    workflow_version TEXT NOT NULL DEFAULT 'unified-research:v1',
    failure_code TEXT,
    failure_explanation TEXT,
    retryable BOOLEAN NOT NULL DEFAULT FALSE,
    failed_at TIMESTAMPTZ,
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
CREATE TABLE IF NOT EXISTS research_cleanup_audits (
    id UUID PRIMARY KEY,
    cleanup_name TEXT NOT NULL UNIQUE,
    retention_rule TEXT NOT NULL,
    deleted_run_count INTEGER NOT NULL CHECK (deleted_run_count >= 0),
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT now()
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
    preflight_final_url TEXT,
    preflight_redirect_result TEXT,
    preflight_trust_disposition TEXT,
    UNIQUE (run_id, rank)
);
CREATE TABLE IF NOT EXISTS research_evidence (
    id UUID PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES research_runs(id) ON DELETE CASCADE,
    url TEXT NOT NULL,
    requested_url TEXT,
    redirect_result TEXT,
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
CREATE TABLE IF NOT EXISTS research_status_transitions (
    id UUID PRIMARY KEY,
    research_run_id UUID NOT NULL REFERENCES research_runs(id) ON DELETE CASCADE,
    prior_status TEXT NOT NULL,
    next_status TEXT NOT NULL,
    prior_status_version INTEGER NOT NULL CHECK (prior_status_version >= 0),
    next_status_version INTEGER NOT NULL CHECK (next_status_version > 0),
    workflow_version TEXT NOT NULL,
    transition_id UUID NOT NULL UNIQUE,
    reason TEXT NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS research_checkpoint_cleanups (
    id UUID PRIMARY KEY,
    research_run_id UUID NOT NULL REFERENCES research_runs(id) ON DELETE CASCADE,
    outcome TEXT NOT NULL CHECK (outcome IN ('succeeded', 'failed')),
    explanation TEXT,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS research_workflow_continuations (
    idempotency_key TEXT PRIMARY KEY,
    research_run_id UUID NOT NULL REFERENCES research_runs(id) ON DELETE CASCADE,
    execution_id TEXT NOT NULL,
    wait_type TEXT NOT NULL CHECK (wait_type IN ('candidate_preflight', 'evidence_summary')),
    outcome TEXT NOT NULL CHECK (outcome IN ('completed', 'failed')),
    status TEXT NOT NULL CHECK (status IN ('accepted', 'completed', 'stale', 'failed')),
    explanation TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
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
ALTER TABLE research_runs ADD COLUMN IF NOT EXISTS status_version INTEGER NOT NULL DEFAULT 0;
ALTER TABLE research_runs ADD COLUMN IF NOT EXISTS failed_stage TEXT;
ALTER TABLE research_runs ADD COLUMN IF NOT EXISTS workflow_version TEXT NOT NULL
    DEFAULT 'unified-research:v1';
ALTER TABLE research_runs ADD COLUMN IF NOT EXISTS failure_code TEXT;
ALTER TABLE research_runs ADD COLUMN IF NOT EXISTS failure_explanation TEXT;
ALTER TABLE research_runs ADD COLUMN IF NOT EXISTS retryable BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE research_runs ADD COLUMN IF NOT EXISTS failed_at TIMESTAMPTZ;
ALTER TABLE mcp_tool_audit_events ADD COLUMN IF NOT EXISTS workspace_id UUID;
ALTER TABLE mcp_tool_audit_events ADD COLUMN IF NOT EXISTS research_run_id UUID;
ALTER TABLE mcp_tool_audit_events ADD COLUMN IF NOT EXISTS runtime_run_id UUID;
ALTER TABLE mcp_tool_audit_events ADD COLUMN IF NOT EXISTS runtime_step_id UUID;
ALTER TABLE mcp_tool_audit_events ADD COLUMN IF NOT EXISTS authorization_decision_id UUID;
ALTER TABLE mcp_tool_audit_events ADD COLUMN IF NOT EXISTS resource_type TEXT;
ALTER TABLE mcp_tool_audit_events ADD COLUMN IF NOT EXISTS resource_id TEXT;
ALTER TABLE research_sources
    ADD COLUMN IF NOT EXISTS preflight_status TEXT NOT NULL DEFAULT 'pending';
ALTER TABLE research_sources ADD COLUMN IF NOT EXISTS preflight_reason TEXT;
ALTER TABLE research_sources ADD COLUMN IF NOT EXISTS preflight_checked_at TIMESTAMPTZ;
ALTER TABLE research_sources ADD COLUMN IF NOT EXISTS preflight_content_type TEXT;
ALTER TABLE research_sources ADD COLUMN IF NOT EXISTS preflight_content_hash TEXT;
ALTER TABLE research_sources ADD COLUMN IF NOT EXISTS preflight_final_url TEXT;
ALTER TABLE research_sources ADD COLUMN IF NOT EXISTS preflight_redirect_result TEXT;
ALTER TABLE research_sources ADD COLUMN IF NOT EXISTS preflight_trust_disposition TEXT;
ALTER TABLE research_evidence ADD COLUMN IF NOT EXISTS requested_url TEXT;
ALTER TABLE research_evidence ADD COLUMN IF NOT EXISTS redirect_result TEXT;
ALTER TABLE research_runs DROP CONSTRAINT IF EXISTS research_runs_status_check;
UPDATE research_runs SET status = CASE status
    WHEN 'searching' THEN 'discovering'
    WHEN 'preflighting' THEN 'acquiring'
    WHEN 'ready' THEN 'completed'
    ELSE status
END;
ALTER TABLE research_runs ADD CONSTRAINT research_runs_status_check CHECK (
    status IN ('planning', 'discovering', 'acquiring', 'awaiting_review',
               'evaluating_relevance', 'summarizing', 'assessing_coverage',
               'reporting', 'completed', 'failed')
);
CREATE INDEX IF NOT EXISTS research_status_transitions_run_idx
    ON research_status_transitions(research_run_id, occurred_at);
CREATE INDEX IF NOT EXISTS research_checkpoint_cleanups_run_idx
    ON research_checkpoint_cleanups(research_run_id, occurred_at DESC);
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

RESEARCH_STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
    "planning": frozenset({"discovering", "failed"}),
    "discovering": frozenset({
        "acquiring", "evaluating_relevance", "assessing_coverage", "failed"
    }),
    "acquiring": frozenset({
        "awaiting_review", "evaluating_relevance", "assessing_coverage", "failed"
    }),
    "awaiting_review": frozenset({"evaluating_relevance", "assessing_coverage", "failed"}),
    "evaluating_relevance": frozenset({
        "awaiting_review", "summarizing", "assessing_coverage", "failed"
    }),
    "summarizing": frozenset({"assessing_coverage", "failed"}),
    "assessing_coverage": frozenset({"discovering", "reporting", "failed"}),
    "reporting": frozenset({"completed", "failed"}),
    "completed": frozenset(),
    "failed": frozenset({
        "planning", "discovering", "acquiring", "awaiting_review",
        "evaluating_relevance", "summarizing", "assessing_coverage", "reporting"
    }),
}


class ResearchStatusTransitionError(ValueError):
    """Raised when a caller requests a transition outside the approved table."""


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
                    await self._prune_obsolete_target_runs(connection)
            except (asyncpg.PostgresError, OSError) as error:
                if self._pool is not None:
                    await self._pool.close()
                    self._pool = None
                raise ResearchStoreUnavailable("Research persistence is unavailable.") from error
        return self._pool

    async def _prune_obsolete_target_runs(self, connection: asyncpg.Connection) -> None:
        """Remove legacy repeated targets as complete, auditable provenance units."""

        cleanup_name = "deduplicate_obsolete_target_runs_v1"
        async with connection.transaction():
            already_completed = await connection.fetchval(
                "SELECT 1 FROM research_cleanup_audits WHERE cleanup_name = $1",
                cleanup_name,
            )
            if already_completed:
                return
            deleted_runs = await connection.fetch(
                """DELETE FROM research_runs AS obsolete
                   USING research_target_keys AS target
                   WHERE obsolete.workspace_id = target.workspace_id
                     AND lower(regexp_replace(btrim(obsolete.question), '\\s+', ' ', 'g'))
                         = target.normalized_question
                     AND obsolete.id <> target.run_id
                   RETURNING obsolete.id"""
            )
            await connection.execute(
                """INSERT INTO research_cleanup_audits
                   (id, cleanup_name, retention_rule, deleted_run_count)
                   VALUES ($1, $2, $3, $4)""",
                uuid4(),
                cleanup_name,
                (
                    "retain the target-keyed run; delete older repeated target runs "
                    "with dependent provenance"
                ),
                len(deleted_runs),
            )

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
                """SELECT runs.*
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
                   VALUES ($1, $2, $3, 'planning')
                   RETURNING *""",
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

    async def transition_status(
        self,
        run_id: UUID,
        expected_status: str,
        expected_version: int,
        next_status: str,
        transition_id: UUID,
        reason: str,
        *,
        failed_stage: str | None = None,
        failure_code: str | None = None,
        failure_explanation: str | None = None,
        retryable: bool = False,
    ) -> bool:
        """Advance official status once; stale writers leave it unchanged."""

        pool = await self._connection_pool()
        async with pool.acquire() as connection, connection.transaction():
            prior = await connection.fetchrow(
                "SELECT status, status_version, failed_stage, workflow_version "
                "FROM research_runs "
                "WHERE id = $1 FOR UPDATE",
                run_id,
            )
            if prior is None:
                raise KeyError(run_id)
            existing = await connection.fetchval(
                "SELECT 1 FROM research_status_transitions WHERE transition_id = $1",
                transition_id,
            )
            if existing:
                return True
            if prior["status"] != expected_status or prior["status_version"] != expected_version:
                await self._append_audit(
                    connection,
                    run_id,
                    "research.status.conflict",
                    {
                        "expected_status": expected_status,
                        "expected_version": expected_version,
                        "actual_status": prior["status"],
                        "actual_version": prior["status_version"],
                        "requested_status": next_status,
                        "transition_id": str(transition_id),
                    },
                )
                return False
            allowed = RESEARCH_STATUS_TRANSITIONS.get(expected_status, frozenset())
            if next_status not in allowed:
                raise ResearchStatusTransitionError(
                    f"Cannot transition research from {expected_status} to {next_status}."
                )
            if expected_status == "failed" and next_status != prior["failed_stage"]:
                raise ResearchStatusTransitionError(
                    "A failed research run may resume only from its stored failed stage."
                )
            next_version = expected_version + 1
            await connection.execute(
                """UPDATE research_runs
                   SET status = $2, status_version = $3, failed_stage = $4,
                       failure_code = $5, failure_explanation = $6, retryable = $7,
                       failed_at = CASE WHEN $2 = 'failed' THEN now() ELSE NULL END,
                       updated_at = now()
                   WHERE id = $1""",
                run_id,
                next_status,
                next_version,
                failed_stage,
                failure_code,
                failure_explanation,
                retryable,
            )
            await connection.execute(
                """INSERT INTO research_status_transitions
                   (id, research_run_id, prior_status, next_status,
                    prior_status_version, next_status_version, workflow_version,
                    transition_id, reason)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)""",
                uuid4(),
                run_id,
                expected_status,
                next_status,
                expected_version,
                next_version,
                prior["workflow_version"],
                transition_id,
                reason,
            )
        return True

    async def record_mcp_tool_event(
        self,
        workspace_id: UUID,
        request_id: str | None,
        tool_name: str,
        outcome: str,
        details: dict[str, object],
        *,
        research_run_id: UUID | None = None,
        runtime_run_id: UUID | None = None,
        runtime_step_id: UUID | None = None,
        authorization_decision_id: UUID | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
    ) -> None:
        """Append one direct MCP execution outcome without creating a research run."""

        pool = await self._connection_pool()
        async with pool.acquire() as connection:
            await connection.execute(
                """INSERT INTO mcp_tool_audit_events
                   (id, workspace_id, request_id, tool_name, outcome, details,
                    research_run_id, runtime_run_id, runtime_step_id,
                    authorization_decision_id, resource_type, resource_id)
                   VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7, $8, $9, $10, $11, $12)""",
                uuid4(),
                workspace_id,
                request_id,
                tool_name,
                outcome,
                json.dumps(self._redact(details)),
                research_run_id,
                runtime_run_id,
                runtime_step_id,
                authorization_decision_id,
                resource_type,
                resource_id,
            )

    async def record_checkpoint_cleanup(
        self, run_id: UUID, outcome: str, explanation: str | None = None
    ) -> None:
        """Audit checkpoint cleanup without changing the business outcome."""

        pool = await self._connection_pool()
        async with pool.acquire() as connection:
            await connection.execute(
                """INSERT INTO research_checkpoint_cleanups
                   (id, research_run_id, outcome, explanation)
                   VALUES ($1, $2, $3, $4)""",
                uuid4(),
                run_id,
                outcome,
                explanation,
            )

    async def claim_workflow_continuation(
        self,
        idempotency_key: str,
        research_run_id: UUID,
        execution_id: str,
        wait_type: str,
        outcome: str,
    ) -> bool:
        """Claim one Temporal completion once without changing research status."""

        pool = await self._connection_pool()
        async with pool.acquire() as connection, connection.transaction():
            await connection.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended($1, 0))",
                idempotency_key,
            )
            existing = await connection.fetchval(
                "SELECT status FROM research_workflow_continuations WHERE idempotency_key = $1",
                idempotency_key,
            )
            if existing is not None:
                return existing == "accepted"
            await connection.execute(
                """INSERT INTO research_workflow_continuations
                   (idempotency_key, research_run_id, execution_id, wait_type,
                    outcome, status)
                   VALUES ($1, $2, $3, $4, $5, 'accepted')""",
                idempotency_key,
                research_run_id,
                execution_id,
                wait_type,
                outcome,
            )
        return True

    async def finish_workflow_continuation(
        self, idempotency_key: str, status: str, explanation: str | None = None
    ) -> None:
        """Record a bounded continuation result without becoming business authority."""

        pool = await self._connection_pool()
        async with pool.acquire() as connection:
            await connection.execute(
                """UPDATE research_workflow_continuations
                   SET status = $2, explanation = $3, updated_at = now()
                   WHERE idempotency_key = $1""",
                idempotency_key,
                status,
                explanation,
            )

    async def checkpoint_cleanup_candidates(self, limit: int = 100) -> list[UUID]:
        """Return oldest completed runs without a successful cleanup audit."""

        pool = await self._connection_pool()
        async with pool.acquire() as connection:
            rows = await connection.fetch(
                """SELECT runs.id
                   FROM research_runs AS runs
                   WHERE runs.status = 'completed'
                     AND NOT EXISTS (
                         SELECT 1 FROM research_checkpoint_cleanups AS cleanup
                         WHERE cleanup.research_run_id = runs.id
                           AND cleanup.outcome = 'succeeded'
                     )
                   ORDER BY runs.updated_at
                   LIMIT $1""",
                limit,
            )
        return [row["id"] for row in rows]

    async def checkpoint_cleanup_backlog(self) -> int:
        pool = await self._connection_pool()
        async with pool.acquire() as connection:
            return int(
                await connection.fetchval(
                    """SELECT COUNT(*)
                       FROM research_runs AS runs
                       WHERE runs.status = 'completed'
                         AND NOT EXISTS (
                             SELECT 1 FROM research_checkpoint_cleanups AS cleanup
                             WHERE cleanup.research_run_id = runs.id
                               AND cleanup.outcome = 'succeeded'
                         )"""
                )
            )

    async def list_mcp_tool_events(
        self, workspace_id: UUID, limit: int
    ) -> list[McpToolAuditEvent]:
        """Return recent direct MCP outcomes without retaining retrieved page content."""

        pool = await self._connection_pool()
        async with pool.acquire() as connection:
            rows = await connection.fetch(
                """SELECT id, request_id, research_run_id, runtime_run_id,
                          runtime_step_id, authorization_decision_id, resource_type,
                          resource_id, tool_name, outcome, occurred_at, details
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

    async def save_new_sources(
        self, run_id: UUID, sources: list[SourceCandidate], requested_max_results: int
    ) -> list[SourceCandidate]:
        """Append only workspace-new source URLs to the canonical target."""

        pool = await self._connection_pool()
        async with pool.acquire() as connection, connection.transaction():
            workspace_id = await connection.fetchval(
                "SELECT workspace_id FROM research_runs WHERE id = $1", run_id
            )
            if workspace_id is None:
                raise KeyError(run_id)
            await connection.execute(
                "SELECT 1 FROM research_runs WHERE id = $1 FOR UPDATE", run_id
            )
            known_urls = set(
                await connection.fetchval(
                    """SELECT COALESCE(array_agg(DISTINCT sources.url), ARRAY[]::text[])
                       FROM research_sources AS sources
                       JOIN research_runs AS owner ON owner.id = sources.run_id
                       WHERE owner.workspace_id = $1""",
                    workspace_id,
                )
            )
            next_rank = await connection.fetchval(
                "SELECT COALESCE(MAX(rank), 0) + 1 FROM research_sources WHERE run_id = $1",
                run_id,
            )
            persisted_sources: list[SourceCandidate] = []
            for source in sources:
                if source.url in known_urls:
                    continue
                persisted = source.model_copy(update={"rank": next_rank})
                await connection.execute(
                    """INSERT INTO research_sources
                       (id, run_id, rank, title, url, snippet, engine, preflight_status,
                        preflight_reason, preflight_checked_at, preflight_content_type,
                        preflight_content_hash, preflight_final_url, preflight_redirect_result,
                        preflight_trust_disposition)
                       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)""",
                    uuid4(),
                    run_id,
                    persisted.rank,
                    persisted.title,
                    persisted.url,
                    persisted.snippet,
                    persisted.engine,
                    "pending",
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                )
                known_urls.add(source.url)
                next_rank += 1
                persisted_sources.append(persisted)
            await self._append_audit(
                connection,
                run_id,
                "research.search.completed",
                {
                    "discovered_source_count": len(sources),
                    "new_source_count": len(persisted_sources),
                    "known_source_count": len(sources) - len(persisted_sources),
                    "requested_max_results": requested_max_results,
                    "new_source_urls": [source.url for source in persisted_sources],
                },
            )
        return persisted_sources

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
        final_url: str | None = None,
        redirect_result: str | None = None,
        trust_disposition: str | None = None,
    ) -> None:
        """Persist one candidate result even when no evidence can be retained."""

        pool = await self._connection_pool()
        async with pool.acquire() as connection, connection.transaction():
            await connection.execute(
                """UPDATE research_sources
                   SET preflight_status = $3, preflight_reason = $4, preflight_checked_at = now(),
                       preflight_content_type = $5, preflight_content_hash = $6,
                       preflight_final_url = $7, preflight_redirect_result = $8,
                       preflight_trust_disposition = $9
                   WHERE run_id = $1 AND url = $2""",
                run_id,
                url,
                status,
                reason,
                content_type,
                content_hash,
                final_url,
                redirect_result,
                trust_disposition,
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
                    "final_url": final_url,
                    "redirect_result": redirect_result,
                    "trust_disposition": trust_disposition,
                },
            )
            await connection.execute(
                "UPDATE research_runs SET updated_at = now() WHERE id = $1", run_id
            )

    async def record_candidate_preflight_route(
        self, run_id: UUID, route: str, source_count: int
    ) -> None:
        """Record the platform-selected execution route without using Temporal history."""

        pool = await self._connection_pool()
        async with pool.acquire() as connection, connection.transaction():
            await self._append_audit(
                connection,
                run_id,
                "research.candidate.preflight.routed",
                {"route": route, "source_count": source_count},
            )

    async def complete_candidate_preflight(self, run_id: UUID) -> None:
        """Record preflight facts without advancing the research workflow state.

        The unified LangGraph workflow owns every operator-visible research
        status transition. Preflight is a durable activity that records its
        outcome, then returns control to that workflow.
        """

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

    async def fail_candidate_preflight(self, run_id: UUID, reason: str) -> None:
        """Record preflight failure facts; the graph records the run failure."""

        pool = await self._connection_pool()
        async with pool.acquire() as connection, connection.transaction():
            await self._append_audit(
                connection, run_id, "research.candidate.preflight.failed", {"reason": reason}
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
                    {
                        "requested_url": evidence.requested_url,
                        "url": evidence.url,
                        "content_hash": evidence.content_hash,
                        "redirect_result": evidence.redirect_result,
                    },
                )
                return
            await connection.execute(
                """INSERT INTO research_evidence
                   (id, run_id, url, requested_url, redirect_result, retrieved_at, content_type,
                    text, content_hash, extraction_method)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)""",
                uuid4(),
                run_id,
                evidence.url,
                evidence.requested_url,
                evidence.redirect_result,
                evidence.retrieved_at,
                evidence.content_type,
                evidence.text,
                evidence.content_hash,
                evidence.extraction_method,
            )
            await self._append_audit(
                connection, run_id, "research.evidence.extracted",
                {
                    "requested_url": evidence.requested_url,
                    "url": evidence.url,
                    "content_hash": evidence.content_hash,
                    "redirect_result": evidence.redirect_result,
                },
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
                          preflight_final_url, preflight_redirect_result,
                          preflight_trust_disposition FROM research_sources
                   WHERE run_id = $1 ORDER BY rank""",
                run_id,
            )
            evidence = await connection.fetch(
                """SELECT url, requested_url, redirect_result, retrieved_at, content_type, text,
                          content_hash, extraction_method
                   FROM (
                       SELECT DISTINCT ON (candidate.url)
                           evidence.url, evidence.requested_url, evidence.redirect_result,
                           evidence.retrieved_at, evidence.content_type, evidence.text,
                           evidence.content_hash, evidence.extraction_method
                       FROM research_evidence AS evidence
                       JOIN research_runs AS owner ON owner.id = evidence.run_id
                       JOIN research_sources AS candidate
                         ON candidate.run_id = $1
                        AND candidate.preflight_content_hash = evidence.content_hash
                        AND (candidate.preflight_final_url = evidence.url
                             OR (candidate.preflight_final_url IS NULL
                                 AND candidate.url = evidence.url))
                       WHERE candidate.run_id = $1 AND owner.workspace_id = $2
                       ORDER BY candidate.url, evidence.retrieved_at DESC
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
                """SELECT runs.id, runs.question, runs.status, runs.status_version,
                          runs.failed_stage, runs.failure_code, runs.failure_explanation,
                          runs.retryable, runs.failed_at, runs.created_at, runs.updated_at,
                          COUNT(DISTINCT sources.id)::integer AS source_count,
                          COUNT(DISTINCT evidence.id)::integer AS evidence_count
                   FROM research_runs AS runs
                   LEFT JOIN research_sources AS sources ON sources.run_id = runs.id
                   LEFT JOIN research_sources AS evidence_source ON evidence_source.run_id = runs.id
                   LEFT JOIN research_evidence AS evidence
                     ON evidence.content_hash = evidence_source.preflight_content_hash
                    AND (evidence.url = evidence_source.preflight_final_url
                         OR (evidence_source.preflight_final_url IS NULL
                             AND evidence.url = evidence_source.url))
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
