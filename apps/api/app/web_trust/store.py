"""Postgres persistence for immutable local web-trust evaluations and overrides."""

import json
from collections.abc import Callable
from datetime import datetime
from uuid import UUID, uuid4

import asyncpg

from app.web_trust.contracts import EvidenceTrustEvaluation, TrustRuleOutcome

SCHEMA = """
CREATE TABLE IF NOT EXISTS web_trust_policy_versions (
    id UUID PRIMARY KEY,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    version TEXT NOT NULL,
    rules JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (workspace_id, version)
);
CREATE TABLE IF NOT EXISTS web_evidence_trust_evaluations (
    id UUID PRIMARY KEY,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    run_id UUID NOT NULL REFERENCES research_runs(id) ON DELETE CASCADE,
    source_url TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    disposition TEXT NOT NULL CHECK (
        disposition IN ('eligible', 'eligible_with_notice', 'review_required', 'blocked')
    ),
    rule_outcomes JSONB NOT NULL,
    component_version TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS web_evidence_trust_overrides (
    id UUID PRIMARY KEY,
    evaluation_id UUID NOT NULL REFERENCES web_evidence_trust_evaluations(id) ON DELETE CASCADE,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    actor_user_id UUID NOT NULL REFERENCES platform_users(id) ON DELETE RESTRICT,
    reason TEXT NOT NULL,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS web_evidence_trust_evaluations_lookup_idx
    ON web_evidence_trust_evaluations(run_id, source_url, content_hash, created_at DESC);
CREATE INDEX IF NOT EXISTS web_evidence_trust_overrides_active_idx
    ON web_evidence_trust_overrides(evaluation_id, created_at DESC);
"""


class WebTrustStoreUnavailable(RuntimeError):
    """Raised when local web-trust persistence cannot be used."""


class WebTrustStore:
    """Workspace-scoped persistence for immutable trust decisions."""

    def __init__(
        self, database_url: str | None, redact: Callable[[object], object] | None = None
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
            raise WebTrustStoreUnavailable("Web-trust persistence is not configured.")
        if self._pool is None:
            try:
                self._pool = await asyncpg.create_pool(self._database_url, min_size=1, max_size=5)
                async with self._pool.acquire() as connection:
                    await connection.execute(SCHEMA)
            except (asyncpg.PostgresError, OSError) as error:
                if self._pool is not None:
                    await self._pool.close()
                    self._pool = None
                raise WebTrustStoreUnavailable("Web-trust persistence is unavailable.") from error
        return self._pool

    async def ensure_default_policy(self, workspace_id: UUID, rules: dict[str, object]) -> None:
        pool = await self._connection_pool()
        async with pool.acquire() as connection:
            await connection.execute(
                """INSERT INTO web_trust_policy_versions (id, workspace_id, version, rules)
                   VALUES ($1, $2, 'local-default-v1', $3::jsonb)
                   ON CONFLICT (workspace_id, version) DO NOTHING""",
                uuid4(), workspace_id, json.dumps(self._redact(rules)),
            )

    async def latest_evaluation(
        self, workspace_id: UUID, run_id: UUID, source_url: str, content_hash: str
    ) -> EvidenceTrustEvaluation | None:
        pool = await self._connection_pool()
        async with pool.acquire() as connection:
            row = await connection.fetchrow(
                """SELECT evaluation.*, override.id AS override_id,
                          override.reason AS override_reason,
                          override.expires_at AS override_expires_at
                   FROM web_evidence_trust_evaluations AS evaluation
                   LEFT JOIN LATERAL (
                       SELECT id, reason, expires_at
                       FROM web_evidence_trust_overrides
                       WHERE evaluation_id = evaluation.id
                         AND (expires_at IS NULL OR expires_at > now())
                       ORDER BY created_at DESC LIMIT 1
                   ) AS override ON TRUE
                   WHERE evaluation.workspace_id = $1 AND evaluation.run_id = $2
                     AND evaluation.source_url = $3 AND evaluation.content_hash = $4
                   ORDER BY evaluation.created_at DESC LIMIT 1""",
                workspace_id, run_id, source_url, content_hash,
            )
        return self._to_evaluation(row) if row is not None else None

    async def record_evaluation(
        self,
        workspace_id: UUID,
        run_id: UUID,
        source_url: str,
        content_hash: str,
        disposition: str,
        rule_outcomes: list[TrustRuleOutcome],
        component_version: str,
    ) -> EvidenceTrustEvaluation:
        pool = await self._connection_pool()
        async with pool.acquire() as connection:
            row = await connection.fetchrow(
                """INSERT INTO web_evidence_trust_evaluations
                   (id, workspace_id, run_id, source_url, content_hash, policy_version,
                    disposition, rule_outcomes, component_version)
                   VALUES ($1, $2, $3, $4, $5, 'local-default-v1', $6, $7::jsonb, $8)
                   RETURNING *""",
                uuid4(), workspace_id, run_id, source_url, content_hash, disposition,
                json.dumps([outcome.model_dump() for outcome in rule_outcomes]), component_version,
            )
        return self._to_evaluation(row)

    async def list_latest_evaluations(
        self, workspace_id: UUID, run_id: UUID
    ) -> list[EvidenceTrustEvaluation]:
        pool = await self._connection_pool()
        async with pool.acquire() as connection:
            rows = await connection.fetch(
                """SELECT DISTINCT ON (evaluation.source_url, evaluation.content_hash)
                          evaluation.*, override.id AS override_id,
                          override.reason AS override_reason,
                          override.expires_at AS override_expires_at
                   FROM web_evidence_trust_evaluations AS evaluation
                   LEFT JOIN LATERAL (
                       SELECT id, reason, expires_at
                       FROM web_evidence_trust_overrides
                       WHERE evaluation_id = evaluation.id
                         AND (expires_at IS NULL OR expires_at > now())
                       ORDER BY created_at DESC LIMIT 1
                   ) AS override ON TRUE
                   WHERE evaluation.workspace_id = $1 AND evaluation.run_id = $2
                   ORDER BY evaluation.source_url, evaluation.content_hash,
                            evaluation.created_at DESC""",
                workspace_id, run_id,
            )
        return [self._to_evaluation(row) for row in rows]

    async def accept_evaluation(
        self,
        workspace_id: UUID,
        run_id: UUID,
        source_url: str,
        content_hash: str,
        actor_user_id: UUID,
        reason: str,
        expires_at: datetime | None,
    ) -> EvidenceTrustEvaluation | None:
        evaluation = await self.latest_evaluation(workspace_id, run_id, source_url, content_hash)
        if evaluation is None:
            return None
        pool = await self._connection_pool()
        async with pool.acquire() as connection:
            await connection.execute(
                """INSERT INTO web_evidence_trust_overrides
                   (id, evaluation_id, workspace_id, actor_user_id, reason, expires_at)
                   VALUES ($1, $2, $3, $4, $5, $6)""",
                uuid4(), evaluation.id, workspace_id, actor_user_id, reason, expires_at,
            )
        return await self.latest_evaluation(workspace_id, run_id, source_url, content_hash)

    @staticmethod
    def _to_evaluation(row: asyncpg.Record) -> EvidenceTrustEvaluation:
        values = dict(row)
        raw_outcomes = values.pop("rule_outcomes")
        if isinstance(raw_outcomes, str):
            raw_outcomes = json.loads(raw_outcomes)
        override_id = values.pop("override_id", None)
        override_reason = values.pop("override_reason", None)
        override_expires_at = values.pop("override_expires_at", None)
        base_disposition = values.pop("disposition")
        return EvidenceTrustEvaluation(
            **values,
            disposition="eligible" if override_id is not None else base_disposition,
            base_disposition=base_disposition,
            rule_outcomes=[TrustRuleOutcome(**item) for item in raw_outcomes],
            override_id=override_id,
            override_reason=override_reason,
            override_expires_at=override_expires_at,
        )
