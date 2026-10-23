"""Postgres records for research topics, relevance, and evidence coverage."""

import hashlib
import json
import re
from collections.abc import Mapping
from uuid import UUID, uuid4

import asyncpg

from app.agentic_research.contracts import (
    FinalReportAttempt,
    RelevanceDecision,
    ReportExclusion,
    ReportExclusionReasonCode,
    ReportInput,
    ReportQualityReason,
    ReportSupportingSource,
    ResearchReport,
    ResearchReportSource,
    TopicAttentionItem,
    TopicCoverage,
    TopicCoverageAssessment,
    TopicCoverageEvidence,
    TopicCoverageFacts,
    TopicPlan,
    TopicQuestionSummary,
    TopicRelevanceInput,
    TopicRelevanceRecord,
    TopicSourceAssociation,
    TopicSourceExclusion,
    TopicSourceLibrary,
    TopicSourceSummary,
    TopicWikiRead,
    TopicWikiRevision,
    TopicWikiSource,
    TopicWorkspace,
    TopicWorkspaceSummary,
    assess_topic_coverage,
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS agentic_research_topics (
    id UUID PRIMARY KEY,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    run_id UUID NOT NULL REFERENCES research_runs(id) ON DELETE CASCADE,
    topic_id TEXT NOT NULL,
    topic TEXT NOT NULL,
    search_query TEXT NOT NULL,
    position INTEGER NOT NULL CHECK (position BETWEEN 1 AND 3),
    prompt_version TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (run_id, topic_id)
);
CREATE TABLE IF NOT EXISTS agentic_topic_relevance_decisions (
    id UUID PRIMARY KEY,
    topic_record_id UUID NOT NULL REFERENCES agentic_research_topics(id) ON DELETE CASCADE,
    source_url TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    decision TEXT NOT NULL CHECK (
        decision IN ('relevant', 'not_relevant', 'model_failure')
    ),
    model_name TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    model_output TEXT NOT NULL DEFAULT '',
    failure_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS agentic_topic_coverage_evidence (
    id UUID PRIMARY KEY,
    topic_record_id UUID NOT NULL REFERENCES agentic_research_topics(id) ON DELETE CASCADE,
    source_url TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    evidence_id UUID NOT NULL REFERENCES research_evidence(id) ON DELETE CASCADE,
    trust_evaluation_id UUID NOT NULL
        REFERENCES web_evidence_trust_evaluations(id) ON DELETE CASCADE,
    relevance_decision_id UUID NOT NULL
        REFERENCES agentic_topic_relevance_decisions(id) ON DELETE CASCADE,
    summary_artifact_id UUID NOT NULL
        REFERENCES evidence_summary_artifacts(id) ON DELETE CASCADE,
    qualified_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (topic_record_id, source_url, content_hash)
);
CREATE TABLE IF NOT EXISTS agentic_research_discovered_sources (
    run_id UUID NOT NULL REFERENCES research_runs(id) ON DELETE CASCADE,
    topic_record_id UUID NOT NULL REFERENCES agentic_research_topics(id) ON DELETE CASCADE,
    source_url TEXT NOT NULL,
    result_rank INTEGER NOT NULL CHECK (result_rank BETWEEN 1 AND 50),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (run_id, topic_record_id, source_url)
);
CREATE TABLE IF NOT EXISTS agentic_research_reports (
    id UUID PRIMARY KEY,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    run_id UUID NOT NULL REFERENCES research_runs(id) ON DELETE CASCADE,
    markdown TEXT NOT NULL,
    model_name TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE agentic_research_reports
    ADD COLUMN IF NOT EXISTS contract_version TEXT;
ALTER TABLE agentic_research_reports
    ADD COLUMN IF NOT EXISTS input_fingerprint TEXT;
ALTER TABLE agentic_research_reports
    ADD COLUMN IF NOT EXISTS quality_grade TEXT;
ALTER TABLE agentic_research_reports
    ADD COLUMN IF NOT EXISTS quality_reasons JSONB;
ALTER TABLE agentic_research_reports
    ADD COLUMN IF NOT EXISTS report_origin TEXT;
CREATE TABLE IF NOT EXISTS agentic_research_report_inputs (
    report_id UUID NOT NULL REFERENCES agentic_research_reports(id) ON DELETE CASCADE,
    topic_record_id UUID NOT NULL REFERENCES agentic_research_topics(id) ON DELETE CASCADE,
    topic_id TEXT NOT NULL,
    topic TEXT NOT NULL,
    summary_artifact_id UUID NOT NULL REFERENCES evidence_summary_artifacts(id) ON DELETE CASCADE,
    source_ref TEXT NOT NULL,
    source_url TEXT NOT NULL,
    source_title TEXT NOT NULL,
    summary_text TEXT NOT NULL,
    summary_digest TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    position INTEGER NOT NULL,
    PRIMARY KEY (report_id, source_ref),
    UNIQUE (report_id, topic_record_id, summary_artifact_id)
);
CREATE TABLE IF NOT EXISTS agentic_research_report_contributions (
    report_id UUID NOT NULL REFERENCES agentic_research_reports(id) ON DELETE CASCADE,
    topic_record_id UUID NOT NULL REFERENCES agentic_research_topics(id) ON DELETE CASCADE,
    finding_position INTEGER NOT NULL,
    source_ref TEXT NOT NULL,
    contribution_kind TEXT NOT NULL CHECK (contribution_kind IN ('finding', 'section_source_list')),
    PRIMARY KEY (report_id, topic_record_id, finding_position, source_ref, contribution_kind)
);
CREATE TABLE IF NOT EXISTS agentic_research_report_exclusions (
    report_id UUID NOT NULL REFERENCES agentic_research_reports(id) ON DELETE CASCADE,
    source_url TEXT NOT NULL,
    source_title TEXT NOT NULL,
    topic_ids JSONB NOT NULL,
    reason_code TEXT NOT NULL,
    reason TEXT NOT NULL,
    PRIMARY KEY (report_id, source_url, reason_code)
);
CREATE TABLE IF NOT EXISTS agentic_research_report_attempts (
    id UUID PRIMARY KEY,
    report_id UUID NOT NULL REFERENCES agentic_research_reports(id) ON DELETE CASCADE,
    topic_id TEXT,
    group_index INTEGER NOT NULL DEFAULT 1 CHECK (group_index >= 1),
    attempt_number INTEGER NOT NULL CHECK (attempt_number IN (1, 2)),
    status TEXT NOT NULL CHECK (status IN ('started', 'pass', 'fail', 'unusable')),
    input_fingerprint TEXT NOT NULL,
    model_name TEXT,
    prompt_version TEXT NOT NULL,
    contract_version TEXT NOT NULL,
    raw_response TEXT NOT NULL DEFAULT '',
    validation_errors JSONB NOT NULL DEFAULT '[]'::jsonb,
    duration_ms INTEGER CHECK (duration_ms IS NULL OR duration_ms >= 0),
    input_characters INTEGER NOT NULL DEFAULT 0 CHECK (input_characters >= 0),
    response_characters INTEGER NOT NULL DEFAULT 0 CHECK (response_characters >= 0),
    failure_code TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (report_id, attempt_number)
);
ALTER TABLE agentic_research_report_attempts
    ADD COLUMN IF NOT EXISTS topic_id TEXT;
ALTER TABLE agentic_research_report_attempts
    ADD COLUMN IF NOT EXISTS group_index INTEGER NOT NULL DEFAULT 1;
ALTER TABLE agentic_research_report_attempts
    ADD COLUMN IF NOT EXISTS duration_ms INTEGER;
ALTER TABLE agentic_research_report_attempts
    ADD COLUMN IF NOT EXISTS input_characters INTEGER NOT NULL DEFAULT 0;
ALTER TABLE agentic_research_report_attempts
    ADD COLUMN IF NOT EXISTS response_characters INTEGER NOT NULL DEFAULT 0;
ALTER TABLE agentic_research_report_attempts
    ADD COLUMN IF NOT EXISTS failure_code TEXT;
ALTER TABLE agentic_research_report_attempts
    DROP CONSTRAINT IF EXISTS agentic_research_report_attempts_report_id_attempt_number_key;
DROP INDEX IF EXISTS agentic_research_report_attempts_topic_attempt_idx;
CREATE UNIQUE INDEX IF NOT EXISTS agentic_research_report_attempts_report_attempt_idx
    ON agentic_research_report_attempts(report_id, attempt_number)
    WHERE topic_id IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS agentic_research_report_attempts_topic_attempt_idx
    ON agentic_research_report_attempts(report_id, topic_id, group_index, attempt_number)
    WHERE topic_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS agentic_research_topics_workspace_run_idx
    ON agentic_research_topics(workspace_id, run_id, created_at);
CREATE INDEX IF NOT EXISTS agentic_topic_relevance_lookup_idx
    ON agentic_topic_relevance_decisions(
        topic_record_id, source_url, content_hash, created_at DESC
    );
CREATE INDEX IF NOT EXISTS agentic_topic_coverage_lookup_idx
    ON agentic_topic_coverage_evidence(topic_record_id, qualified_at);
CREATE INDEX IF NOT EXISTS agentic_research_reports_workspace_run_idx
    ON agentic_research_reports(workspace_id, run_id, created_at DESC);
ALTER TABLE agentic_topic_relevance_decisions
    ADD COLUMN IF NOT EXISTS model_output TEXT NOT NULL DEFAULT '';
ALTER TABLE agentic_topic_relevance_decisions
    ADD COLUMN IF NOT EXISTS failure_reason TEXT;
CREATE TABLE IF NOT EXISTS research_topics (
    id UUID PRIMARY KEY,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    current_revision_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (workspace_id, normalized_name)
);
CREATE TABLE IF NOT EXISTS research_topic_runs (
    topic_id UUID NOT NULL REFERENCES research_topics(id) ON DELETE CASCADE,
    run_id UUID NOT NULL UNIQUE REFERENCES research_runs(id) ON DELETE CASCADE,
    input_kind TEXT NOT NULL CHECK (input_kind = 'question'),
    normalized_question TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (topic_id, run_id),
    UNIQUE (topic_id, normalized_question)
);
CREATE TABLE IF NOT EXISTS research_topic_sources (
    topic_id UUID NOT NULL REFERENCES research_topics(id) ON DELETE CASCADE,
    evidence_id UUID NOT NULL REFERENCES research_evidence(id) ON DELETE CASCADE,
    first_run_id UUID NOT NULL REFERENCES research_runs(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (topic_id, evidence_id)
);
CREATE TABLE IF NOT EXISTS research_topic_source_introductions (
    topic_id UUID NOT NULL REFERENCES research_topics(id) ON DELETE CASCADE,
    evidence_id UUID NOT NULL REFERENCES research_evidence(id) ON DELETE CASCADE,
    run_id UUID NOT NULL REFERENCES research_runs(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (topic_id, evidence_id, run_id)
);
CREATE TABLE IF NOT EXISTS research_topic_wiki_revisions (
    id UUID PRIMARY KEY,
    topic_id UUID NOT NULL REFERENCES research_topics(id) ON DELETE CASCADE,
    revision_number INTEGER NOT NULL CHECK (revision_number >= 1),
    triggering_run_id UUID NOT NULL REFERENCES research_runs(id) ON DELETE RESTRICT,
    previous_revision_id UUID REFERENCES research_topic_wiki_revisions(id) ON DELETE RESTRICT,
    markdown TEXT NOT NULL,
    input_fingerprint TEXT NOT NULL,
    model_name TEXT,
    prompt_version TEXT NOT NULL,
    contract_version TEXT NOT NULL,
    quality_grade TEXT NOT NULL CHECK (quality_grade IN ('PASS', 'FAIL')),
    quality_reasons JSONB NOT NULL DEFAULT '[]'::jsonb,
    origin TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (topic_id, revision_number),
    UNIQUE (topic_id, input_fingerprint)
);
ALTER TABLE research_topics
    DROP CONSTRAINT IF EXISTS research_topics_current_revision_id_fkey;
ALTER TABLE research_topics
    ADD CONSTRAINT research_topics_current_revision_id_fkey
    FOREIGN KEY (current_revision_id) REFERENCES research_topic_wiki_revisions(id)
    ON DELETE SET NULL;
CREATE TABLE IF NOT EXISTS research_topic_wiki_revision_inputs (
    revision_id UUID NOT NULL REFERENCES research_topic_wiki_revisions(id) ON DELETE CASCADE,
    summary_artifact_id UUID NOT NULL REFERENCES evidence_summary_artifacts(id) ON DELETE RESTRICT,
    evidence_id UUID NOT NULL REFERENCES research_evidence(id) ON DELETE RESTRICT,
    source_label TEXT NOT NULL,
    source_title TEXT NOT NULL,
    source_url TEXT NOT NULL,
    planned_topic_id TEXT NOT NULL,
    position INTEGER NOT NULL CHECK (position >= 1),
    PRIMARY KEY (revision_id, source_label),
    UNIQUE (revision_id, summary_artifact_id)
);
CREATE TABLE IF NOT EXISTS research_topic_wiki_contributions (
    revision_id UUID NOT NULL REFERENCES research_topic_wiki_revisions(id) ON DELETE CASCADE,
    finding_position INTEGER NOT NULL CHECK (finding_position >= 1),
    source_label TEXT NOT NULL,
    PRIMARY KEY (revision_id, finding_position, source_label)
);
CREATE TABLE IF NOT EXISTS research_topic_wiki_exclusions (
    revision_id UUID NOT NULL REFERENCES research_topic_wiki_revisions(id) ON DELETE CASCADE,
    source_url TEXT NOT NULL,
    source_title TEXT NOT NULL,
    reason_code TEXT NOT NULL,
    reason TEXT NOT NULL,
    PRIMARY KEY (revision_id, source_url, reason_code)
);
CREATE TABLE IF NOT EXISTS research_topic_wiki_updates (
    revision_id UUID PRIMARY KEY REFERENCES research_topic_wiki_revisions(id) ON DELETE CASCADE,
    question TEXT NOT NULL,
    source_additions JSONB NOT NULL DEFAULT '[]'::jsonb,
    source_exclusions JSONB NOT NULL DEFAULT '[]'::jsonb,
    changed_sections JSONB NOT NULL DEFAULT '[]'::jsonb,
    changed_findings JSONB NOT NULL DEFAULT '[]'::jsonb,
    remaining_gaps JSONB NOT NULL DEFAULT '[]'::jsonb,
    change_summary TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS research_topics_workspace_updated_idx
    ON research_topics(workspace_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS research_topic_runs_topic_created_idx
    ON research_topic_runs(topic_id, created_at DESC);
CREATE INDEX IF NOT EXISTS research_topic_wiki_revisions_topic_number_idx
    ON research_topic_wiki_revisions(topic_id, revision_number DESC);
"""

_PUBLISHER_ACCESS_DENIED_MARKERS = (
    "http 403",
    "403",
    "forbidden",
    "rejected automated access",
    "access denied",
)


def _report_exclusion_reason(row: Mapping[str, object]) -> tuple[ReportExclusionReasonCode, str]:
    """Derive the operator-facing exclusion reason from stored platform outcomes."""

    preflight_status = row.get("preflight_status")
    preflight_reason = str(row.get("preflight_reason") or "").casefold()
    preflight_trust_disposition = row.get("preflight_trust_disposition")
    summary_status = row.get("summary_status")
    evidence_sufficient = row.get("evidence_sufficient")
    failure_category = row.get("failure_category")

    if preflight_status == "blocked" or preflight_trust_disposition == "blocked":
        return (
            "blocked_by_trust_policy",
            "Blocked by the local trust workflow.",
        )
    if preflight_status == "review_required":
        return (
            "review_required",
            "Requires recorded human review before use.",
        )
    if preflight_status == "unreachable":
        if any(marker in preflight_reason for marker in _PUBLISHER_ACCESS_DENIED_MARKERS):
            return (
                "access_denied_by_publisher",
                (
                    "The publisher or website rejected automated access before "
                    "usable evidence could be captured."
                ),
            )
        return (
            "unreachable",
            "No usable evidence was captured for report findings.",
        )
    if summary_status == "failed":
        return (
            "summary_failed",
            str(failure_category or "Summary processing did not store a usable source summary."),
        )
    if evidence_sufficient is False:
        return (
            "evidence_insufficient",
            "The captured content was insufficient for report findings.",
        )
    if summary_status == "completed" and evidence_sufficient is not False:
        return (
            "not_relevant_to_planned_topics",
            "It was not relevant to the planned topics for this report.",
        )
    return (
        "unreachable",
        "No usable evidence was captured for report findings.",
    )


def _json_value(value: object, default: object) -> object:
    """Normalise asyncpg JSON values without trusting their runtime representation."""

    if value is None:
        return default
    if isinstance(value, str):
        return json.loads(value)
    return value


def _summary_digest(summary: str) -> str:
    return hashlib.sha256(summary.encode("utf-8")).hexdigest()


def _report_input_fingerprint(inputs: list[ReportInput]) -> str:
    payload = [
        {
            "topic_id": item.topic_id,
            "source_url": item.source_url,
            "content_hash": item.content_hash,
            "summary_artifact_id": str(item.summary_artifact_id),
        }
        for item in inputs
    ]
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _current_report_fingerprint(
    inputs: list[ReportInput], coverage: list[TopicCoverage]
) -> str:
    """Match the reporting service fingerprint without creating a service dependency."""

    payload = {
        "topics": [(item.topic_id, item.status) for item in coverage],
        "inputs": [
            (item.topic_id, item.source_url, item.content_hash, str(item.summary_artifact_id))
            for item in inputs
        ],
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


_COVERAGE_FACTS_QUERY = """
SELECT topic.id AS topic_record_id,
       (
           SELECT evidence.id
           FROM research_evidence AS evidence
           JOIN research_runs AS evidence_run ON evidence_run.id = evidence.run_id
           WHERE evidence_run.workspace_id = $1
             AND evidence.url = $4 AND evidence.content_hash = $5
             AND length(btrim(evidence.text)) > 0
           ORDER BY evidence.retrieved_at DESC
           LIMIT 1
       ) AS evidence_id,
       (
           SELECT latest_evaluation.id
           FROM (
               SELECT evaluation.id, evaluation.disposition,
                      active_override.id AS override_id,
                      active_override.outcome AS override_outcome
               FROM web_evidence_trust_evaluations AS evaluation
               LEFT JOIN LATERAL (
                   SELECT override.id, override.outcome
                   FROM web_evidence_trust_overrides AS override
                   WHERE override.evaluation_id = evaluation.id
                     AND (override.expires_at IS NULL OR override.expires_at > now())
                   ORDER BY override.created_at DESC
                   LIMIT 1
               ) AS active_override ON TRUE
               WHERE evaluation.workspace_id = $1
                 AND evaluation.source_url = $4 AND evaluation.content_hash = $5
               ORDER BY evaluation.created_at DESC
               LIMIT 1
           ) AS latest_evaluation
           WHERE latest_evaluation.disposition IN ('eligible', 'eligible_with_notice')
              OR (
                  latest_evaluation.disposition = 'review_required'
                  AND latest_evaluation.override_id IS NOT NULL
                  AND latest_evaluation.override_outcome = 'accepted'
              )
       ) AS trust_evaluation_id,
       (
           SELECT latest_relevance.id
           FROM (
               SELECT relevance.id, relevance.decision
               FROM agentic_topic_relevance_decisions AS relevance
               WHERE relevance.topic_record_id = topic.id
                 AND relevance.source_url = $4 AND relevance.content_hash = $5
               ORDER BY relevance.created_at DESC
               LIMIT 1
           ) AS latest_relevance
           WHERE latest_relevance.decision = 'relevant'
       ) AS relevance_decision_id,
       (
           SELECT artifact.id
           FROM evidence_summary_artifacts AS artifact
           WHERE artifact.workspace_id = $1
             AND artifact.source_url = $4 AND artifact.content_hash = $5
             AND length(btrim(artifact.summary)) > 0
             AND jsonb_typeof(artifact.keywords) = 'array'
             AND jsonb_array_length(artifact.keywords) > 0
             AND artifact.evidence_sufficient IS TRUE
           ORDER BY artifact.created_at DESC
           LIMIT 1
       ) AS summary_artifact_id
FROM agentic_research_topics AS topic
WHERE topic.workspace_id = $1 AND topic.run_id = $2 AND topic.topic_id = $3
"""


class AgenticResearchStoreUnavailable(RuntimeError):
    """Raised when agentic research persistence cannot be used."""


class TopicPlanConflictError(ValueError):
    """Raised when a stored topic plan would be changed after creation."""


class AgenticResearchStore:
    """Workspace-scoped persistence for bounded agentic research state."""

    def __init__(self, database_url: str | None) -> None:
        self._database_url = database_url
        self._pool: asyncpg.Pool | None = None

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    async def _connection_pool(self) -> asyncpg.Pool:
        if not self._database_url:
            raise AgenticResearchStoreUnavailable(
                "Agentic research persistence is not configured."
            )
        if self._pool is None:
            try:
                self._pool = await asyncpg.create_pool(
                    self._database_url, min_size=1, max_size=5
                )
            except (asyncpg.PostgresError, OSError) as error:
                if self._pool is not None:
                    await self._pool.close()
                    self._pool = None
                raise AgenticResearchStoreUnavailable(
                    "Agentic research persistence is unavailable."
                ) from error
        return self._pool

    async def remove_obsolete_control_tables(self) -> None:
        """Remove superseded control tables after RuntimeService became authoritative."""

        pool = await self._connection_pool()
        async with pool.acquire() as connection, connection.transaction():
            await connection.execute(
                """DROP TABLE IF EXISTS agentic_research_capability_audits;
                   DROP TABLE IF EXISTS agentic_research_source_attempts;
                   DROP TABLE IF EXISTS agentic_research_search_requests;
                   DROP TABLE IF EXISTS agentic_research_control_state;"""
            )

    @staticmethod
    def normalize_topic_name(name: str) -> str:
        """Provide stable workspace-local topic identity without model input."""

        return re.sub(r"\s+", " ", name.strip()).casefold()

    async def create_or_get_topic(
        self, workspace_id: UUID, name: str
    ) -> TopicWorkspaceSummary:
        """Create one durable operator notebook or return its normalized match."""

        normalized_name = self.normalize_topic_name(name)
        if not normalized_name:
            raise ValueError("A topic name is required.")
        pool = await self._connection_pool()
        async with pool.acquire() as connection, connection.transaction():
            await connection.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended($1, 0))",
                f"{workspace_id}:topic:{normalized_name}",
            )
            row = await connection.fetchrow(
                """INSERT INTO research_topics (id, workspace_id, name, normalized_name)
                   VALUES ($1, $2, $3, $4)
                   ON CONFLICT (workspace_id, normalized_name) DO UPDATE
                   SET updated_at = research_topics.updated_at
                   RETURNING id, name, current_revision_id, created_at, updated_at""",
                uuid4(),
                workspace_id,
                name.strip(),
                normalized_name,
            )
        return TopicWorkspaceSummary(**dict(row), latest_run_status=None)

    async def list_topics(
        self, workspace_id: UUID, limit: int = 100
    ) -> list[TopicWorkspaceSummary]:
        """List bounded topic cards using existing run status as a derived value."""

        pool = await self._connection_pool()
        async with pool.acquire() as connection:
            rows = await connection.fetch(
                """SELECT topic.id, topic.name, topic.current_revision_id,
                          topic.created_at, topic.updated_at,
                          recent.status AS latest_run_status
                   FROM research_topics AS topic
                   LEFT JOIN LATERAL (
                       SELECT run.status
                       FROM research_topic_runs AS membership
                       JOIN research_runs AS run ON run.id = membership.run_id
                       WHERE membership.topic_id = topic.id
                       ORDER BY run.updated_at DESC
                       LIMIT 1
                   ) AS recent ON TRUE
                   WHERE topic.workspace_id = $1
                   ORDER BY topic.updated_at DESC, topic.name
                   LIMIT $2""",
                workspace_id,
                limit,
            )
        return [TopicWorkspaceSummary(**dict(row)) for row in rows]

    async def get_topic_workspace(
        self, workspace_id: UUID, topic_id: UUID
    ) -> TopicWorkspace | None:
        """Read Topic metadata and its derived, non-persisted review queue."""

        pool = await self._connection_pool()
        async with pool.acquire() as connection:
            row = await connection.fetchrow(
                """SELECT topic.id, topic.name, topic.current_revision_id,
                          topic.created_at, topic.updated_at,
                          recent.status AS latest_run_status
                   FROM research_topics AS topic
                   LEFT JOIN LATERAL (
                       SELECT run.status
                       FROM research_topic_runs AS membership
                       JOIN research_runs AS run ON run.id = membership.run_id
                       WHERE membership.topic_id = topic.id
                       ORDER BY run.updated_at DESC
                       LIMIT 1
                   ) AS recent ON TRUE
                   WHERE topic.workspace_id = $1 AND topic.id = $2""",
                workspace_id,
                topic_id,
            )
        if row is None:
            return None
        return TopicWorkspace(
            topic=TopicWorkspaceSummary(**dict(row)),
            attention_required=await self.topic_attention_items(workspace_id, topic_id),
        )

    async def topic_attention_items(
        self, workspace_id: UUID, topic_id: UUID
    ) -> list[TopicAttentionItem]:
        """Derive unresolved exact-version evidence decisions for one Topic."""

        pool = await self._connection_pool()
        async with pool.acquire() as connection:
            rows = await connection.fetch(
                """SELECT DISTINCT ON (evaluation.id)
                          evaluation.run_id, evaluation.source_url, evaluation.content_hash,
                          source.title, source.preflight_reason AS reason
                   FROM research_topic_runs AS membership
                   JOIN research_runs AS run ON run.id = membership.run_id
                   JOIN web_evidence_trust_evaluations AS evaluation
                     ON evaluation.run_id = run.id
                   LEFT JOIN LATERAL (
                       SELECT candidate.title, candidate.preflight_reason
                       FROM research_sources AS candidate
                       WHERE candidate.run_id = evaluation.run_id
                         AND COALESCE(candidate.preflight_final_url, candidate.url)
                             = evaluation.source_url
                       ORDER BY candidate.rank
                       LIMIT 1
                   ) AS source ON TRUE
                   LEFT JOIN LATERAL (
                       SELECT override.outcome
                       FROM web_evidence_trust_overrides AS override
                       WHERE override.evaluation_id = evaluation.id
                         AND (override.expires_at IS NULL OR override.expires_at > now())
                       ORDER BY override.created_at DESC
                       LIMIT 1
                   ) AS active_override ON TRUE
                   WHERE membership.topic_id = $2
                     AND run.workspace_id = $1
                     AND evaluation.disposition = 'review_required'
                     AND active_override.outcome IS NULL
                   ORDER BY evaluation.id, evaluation.created_at DESC""",
                workspace_id,
                topic_id,
            )
        return [
            TopicAttentionItem(
                run_id=row["run_id"],
                source_url=row["source_url"],
                content_hash=row["content_hash"],
                title=row["title"] or row["source_url"],
                reason=row["reason"] or "Evidence requires human review before use.",
            )
            for row in rows
        ]

    async def associate_qualified_topic_sources(
        self,
        workspace_id: UUID,
        topic_id: UUID,
        run_id: UUID,
        coverage: list[TopicCoverage],
    ) -> None:
        """Add qualified evidence to one Topic without copying trust or summary state.

        A source enters the notebook only after the existing coverage rule has
        confirmed evidence, trust, relevance, and a usable summary. Replays are
        idempotent: the library retains the first qualifying run and separately
        records every later question that introduced the same evidence version.
        """

        evidence_ids = [
            evidence.evidence_id
            for planned_topic in coverage
            for evidence in planned_topic.evidence
        ]
        if not evidence_ids:
            return
        pool = await self._connection_pool()
        async with pool.acquire() as connection, connection.transaction():
            owns_membership = await connection.fetchval(
                """SELECT 1
                   FROM research_topic_runs AS membership
                   JOIN research_topics AS topic ON topic.id = membership.topic_id
                   WHERE topic.workspace_id = $1
                     AND membership.topic_id = $2
                     AND membership.run_id = $3""",
                workspace_id,
                topic_id,
                run_id,
            )
            if not owns_membership:
                raise KeyError(topic_id)
            for evidence_id in dict.fromkeys(evidence_ids):
                await connection.execute(
                    """INSERT INTO research_topic_sources
                       (topic_id, evidence_id, first_run_id)
                       VALUES ($1, $2, $3)
                       ON CONFLICT (topic_id, evidence_id) DO NOTHING""",
                    topic_id,
                    evidence_id,
                    run_id,
                )
                await connection.execute(
                    """INSERT INTO research_topic_source_introductions
                       (topic_id, evidence_id, run_id)
                       VALUES ($1, $2, $3)
                       ON CONFLICT (topic_id, evidence_id, run_id) DO NOTHING""",
                    topic_id,
                    evidence_id,
                    run_id,
                )

    async def topic_report_inputs(
        self, workspace_id: UUID, topic_id: UUID
    ) -> list[ReportInput]:
        """Read every currently qualified summary retained by one notebook.

        This is deliberately a read model over the existing evidence, trust,
        relevance, and summary records. It does not copy a summary into the
        notebook or decide whether the evidence is trustworthy.
        """

        pool = await self._connection_pool()
        async with pool.acquire() as connection:
            rows = await connection.fetch(
                """SELECT planned.id AS topic_record_id, planned.topic_id, planned.topic,
                          artifact.id AS summary_artifact_id, coverage.source_url,
                          COALESCE(NULLIF(source.title, ''), coverage.source_url) AS source_title,
                          artifact.summary AS summary_text, coverage.content_hash,
                          row_number() OVER (
                              ORDER BY planned.topic, planned.topic_id,
                                       coverage.qualified_at, coverage.source_url
                          )::INTEGER AS position
                   FROM research_topic_runs AS membership
                   JOIN agentic_research_topics AS planned
                     ON planned.run_id = membership.run_id
                   JOIN agentic_topic_coverage_evidence AS coverage
                     ON coverage.topic_record_id = planned.id
                   JOIN evidence_summary_artifacts AS artifact
                     ON artifact.id = coverage.summary_artifact_id
                   LEFT JOIN research_sources AS source
                     ON source.run_id = planned.run_id
                    AND (source.url = coverage.source_url
                         OR source.preflight_final_url = coverage.source_url)
                   WHERE membership.topic_id = $2
                     AND planned.workspace_id = $1
                     AND artifact.evidence_sufficient IS TRUE
                     AND EXISTS (
                         SELECT 1
                         FROM web_evidence_trust_evaluations AS evaluation
                         LEFT JOIN web_evidence_trust_overrides AS active_override
                           ON active_override.evaluation_id = evaluation.id
                          AND active_override.outcome = 'accepted'
                          AND (
                              active_override.expires_at IS NULL
                              OR active_override.expires_at > now()
                          )
                         WHERE evaluation.id = coverage.trust_evaluation_id
                           AND (
                               evaluation.disposition IN ('eligible', 'eligible_with_notice')
                               OR (
                                   evaluation.disposition = 'review_required'
                                   AND active_override.id IS NOT NULL
                               )
                           )
                     )
                   ORDER BY planned.topic, planned.topic_id,
                            coverage.qualified_at, coverage.source_url""",
                workspace_id,
                topic_id,
            )
        # One stored summary artifact is one notebook source. It may have been
        # relevant to more than one short-lived planned topic, but the revision
        # snapshot must retain it only once.
        unique_rows: list[Mapping[str, object]] = []
        seen_artifacts: set[UUID] = set()
        for row in rows:
            artifact_id = row["summary_artifact_id"]
            if artifact_id in seen_artifacts:
                continue
            seen_artifacts.add(artifact_id)
            unique_rows.append(row)
        return [
            ReportInput(**dict(row), source_ref=f"S{index:02d}")
            for index, row in enumerate(unique_rows, start=1)
        ]

    async def get_topic_wiki(
        self, workspace_id: UUID, topic_id: UUID, revision_id: UUID | None = None
    ) -> TopicWikiRead | None:
        """Read the current immutable wiki revision, or one named revision."""

        pool = await self._connection_pool()
        async with pool.acquire() as connection:
            topic = await connection.fetchrow(
                """SELECT current_revision_id FROM research_topics
                   WHERE workspace_id = $1 AND id = $2""",
                workspace_id,
                topic_id,
            )
            if topic is None:
                return None
            selected_revision_id = revision_id or topic["current_revision_id"]
            if selected_revision_id is None:
                return TopicWikiRead(no_qualified_evidence=True)
            row = await connection.fetchrow(
                """SELECT revision.id, revision.topic_id, revision.revision_number,
                          revision.triggering_run_id, revision.previous_revision_id,
                          revision.markdown, revision.input_fingerprint,
                          revision.quality_grade, revision.quality_reasons,
                          revision.created_at, update_record.change_summary,
                          update_record.source_additions, update_record.source_exclusions,
                          update_record.changed_sections, update_record.remaining_gaps
                   FROM research_topic_wiki_revisions AS revision
                   LEFT JOIN research_topic_wiki_updates AS update_record
                     ON update_record.revision_id = revision.id
                   WHERE revision.topic_id = $1 AND revision.id = $2""",
                topic_id,
                selected_revision_id,
            )
            source_rows = [] if row is None else await connection.fetch(
                """SELECT source_label, source_title AS title, source_url AS url
                   FROM research_topic_wiki_revision_inputs
                   WHERE revision_id = $1 ORDER BY position, source_label""",
                selected_revision_id,
            )
        if row is None:
            return None
        revision = dict(row)
        change_summary = revision.pop("change_summary")
        source_additions = _json_value(revision.pop("source_additions"), [])
        source_exclusions = _json_value(revision.pop("source_exclusions"), [])
        changed_sections = _json_value(revision.pop("changed_sections"), [])
        remaining_gaps = _json_value(revision.pop("remaining_gaps"), [])
        revision["quality_reasons"] = _json_value(revision["quality_reasons"], [])
        return TopicWikiRead(
            revision=TopicWikiRevision(**revision),
            change_summary=change_summary,
            previous_revision_id=revision["previous_revision_id"],
            supporting_sources=[TopicWikiSource(**dict(item)) for item in source_rows],
            source_additions=source_additions,
            source_exclusions=[
                {
                    "title": str(item.get("title") or "Source"),
                    "url": str(item.get("url") or ""),
                    "reason_code": str(item.get("reason_code") or "unknown"),
                    "reason": str(item.get("reason") or "No reason was recorded."),
                }
                for item in source_exclusions
                if isinstance(item, dict)
            ],
            changed_sections=changed_sections,
            remaining_gaps=remaining_gaps,
        )

    async def list_topic_wiki_revisions(
        self, workspace_id: UUID, topic_id: UUID, limit: int = 50
    ) -> list[TopicWikiRevision]:
        """List immutable revision headers without loading every Markdown body."""

        pool = await self._connection_pool()
        async with pool.acquire() as connection:
            rows = await connection.fetch(
                """SELECT revision.id, revision.topic_id, revision.revision_number,
                          revision.triggering_run_id, revision.previous_revision_id,
                          revision.markdown, revision.input_fingerprint,
                          revision.quality_grade, revision.quality_reasons,
                          revision.created_at
                   FROM research_topic_wiki_revisions AS revision
                   JOIN research_topics AS topic ON topic.id = revision.topic_id
                   WHERE topic.workspace_id = $1 AND revision.topic_id = $2
                   ORDER BY revision.revision_number DESC LIMIT $3""",
                workspace_id,
                topic_id,
                limit,
            )
        return [
            TopicWikiRevision(
                **{**dict(row), "quality_reasons": _json_value(row["quality_reasons"], [])}
            )
            for row in rows
        ]

    async def list_topic_questions(
        self, workspace_id: UUID, topic_id: UUID, limit: int = 100
    ) -> list[TopicQuestionSummary]:
        """Read question history from the canonical run records for one topic."""

        pool = await self._connection_pool()
        async with pool.acquire() as connection:
            rows = await connection.fetch(
                """SELECT run.id AS run_id, run.question, run.status, run.created_at,
                          run.updated_at, revision.id AS contribution_revision_id
                   FROM research_topic_runs AS membership
                   JOIN research_runs AS run ON run.id = membership.run_id
                   LEFT JOIN research_topic_wiki_revisions AS revision
                     ON revision.topic_id = membership.topic_id
                    AND revision.triggering_run_id = run.id
                   JOIN research_topics AS topic ON topic.id = membership.topic_id
                   WHERE topic.workspace_id = $1 AND membership.topic_id = $2
                   ORDER BY run.created_at DESC LIMIT $3""",
                workspace_id,
                topic_id,
                limit,
            )
        results: list[TopicQuestionSummary] = []
        for row in rows:
            outcome = (
                "contributed"
                if row["contribution_revision_id"] is not None
                else "failed"
                if row["status"] == "failed"
                else "no_change"
                if row["status"] == "completed"
                else "in_progress"
            )
            results.append(TopicQuestionSummary(**dict(row), outcome=outcome))
        return results

    async def list_topic_sources(
        self, workspace_id: UUID, topic_id: UUID, limit: int = 200
    ) -> list[TopicSourceSummary]:
        """Read retained source facts without giving the notebook a second source store."""

        pool = await self._connection_pool()
        async with pool.acquire() as connection:
            rows = await connection.fetch(
                """SELECT source.evidence_id, source.first_run_id,
                          COALESCE(NULLIF(candidate.title, ''), evidence.url) AS title,
                          evidence.url, artifact.summary, artifact.keywords,
                          evaluation.disposition AS trust_disposition,
                          source.created_at AS introduced_at,
                          COALESCE(provenance.questions, ARRAY[]::TEXT[])
                            AS introduced_by_questions
                   FROM research_topic_sources AS source
                   JOIN research_topics AS topic ON topic.id = source.topic_id
                   JOIN research_evidence AS evidence ON evidence.id = source.evidence_id
                   LEFT JOIN LATERAL (
                       SELECT item.title
                       FROM research_sources AS item
                       WHERE item.run_id = source.first_run_id
                         AND (item.url = evidence.url OR item.preflight_final_url = evidence.url)
                       ORDER BY item.rank LIMIT 1
                   ) AS candidate ON TRUE
                   LEFT JOIN LATERAL (
                       SELECT summary, keywords
                       FROM evidence_summary_artifacts
                       WHERE workspace_id = $1 AND source_url = evidence.url
                         AND content_hash = evidence.content_hash
                       ORDER BY created_at DESC LIMIT 1
                   ) AS artifact ON TRUE
                   LEFT JOIN LATERAL (
                       SELECT disposition
                       FROM web_evidence_trust_evaluations
                       WHERE workspace_id = $1 AND source_url = evidence.url
                         AND content_hash = evidence.content_hash
                       ORDER BY created_at DESC LIMIT 1
                   ) AS evaluation ON TRUE
                   LEFT JOIN LATERAL (
                       SELECT array_agg(DISTINCT run.question ORDER BY run.question) AS questions
                       FROM research_topic_source_introductions AS introduction
                       JOIN research_runs AS run ON run.id = introduction.run_id
                       WHERE introduction.topic_id = source.topic_id
                         AND introduction.evidence_id = source.evidence_id
                   ) AS provenance ON TRUE
                   WHERE topic.workspace_id = $1 AND source.topic_id = $2
                   ORDER BY source.created_at DESC, evidence.url LIMIT $3""",
                workspace_id,
                topic_id,
                limit,
            )
        return [
            TopicSourceSummary(
                **{
                    **dict(row),
                    "keywords": _json_value(row["keywords"], []),
                    "introduced_by_questions": list(row["introduced_by_questions"] or []),
                }
            )
            for row in rows
        ]

    async def topic_source_library(
        self, workspace_id: UUID, topic_id: UUID, limit: int = 200
    ) -> TopicSourceLibrary:
        """Return retained evidence plus candidates excluded from wiki use."""

        sources = await self.list_topic_sources(workspace_id, topic_id, limit)
        qualified_urls = {source.url for source in sources}
        pool = await self._connection_pool()
        async with pool.acquire() as connection:
            rows = await connection.fetch(
                """SELECT membership.run_id, candidate.title, candidate.url,
                          COALESCE(candidate.preflight_final_url, candidate.url) AS evidence_url,
                          candidate.preflight_status, candidate.preflight_reason,
                          candidate.preflight_trust_disposition,
                          execution_source.status AS summary_status,
                          execution_source.evidence_sufficient,
                          execution_source.failure_category
                   FROM research_topic_runs AS membership
                   JOIN research_topics AS topic ON topic.id = membership.topic_id
                   JOIN research_sources AS candidate ON candidate.run_id = membership.run_id
                   LEFT JOIN LATERAL (
                       SELECT member.status, member.evidence_sufficient, member.failure_category
                       FROM evidence_summary_execution_sources AS member
                       JOIN evidence_summary_executions AS execution
                         ON execution.id = member.execution_id
                       WHERE execution.workspace_id = $1
                         AND execution.run_id = membership.run_id
                         AND member.url = COALESCE(candidate.preflight_final_url, candidate.url)
                       ORDER BY execution.created_at DESC LIMIT 1
                   ) AS execution_source ON TRUE
                   WHERE topic.workspace_id = $1 AND membership.topic_id = $2
                   ORDER BY candidate.rank, candidate.url LIMIT $3""",
                workspace_id,
                topic_id,
                limit,
            )
        exclusions: list[TopicSourceExclusion] = []
        seen: set[tuple[str, str]] = set()
        for row in rows:
            source_url = str(row["evidence_url"])
            if source_url in qualified_urls:
                continue
            code, reason = _report_exclusion_reason(row)
            key = (source_url, code)
            if key in seen:
                continue
            seen.add(key)
            exclusions.append(
                TopicSourceExclusion(
                    run_id=row["run_id"],
                    title=row["title"] or source_url,
                    url=source_url,
                    reason_code=code,
                    reason=reason,
                )
            )
        return TopicSourceLibrary(sources=sources, exclusions=exclusions)

    async def topic_report_exclusions(
        self, workspace_id: UUID, topic_id: UUID
    ) -> list[ReportExclusion]:
        """Translate topic-library exclusions for an immutable wiki snapshot."""

        library = await self.topic_source_library(workspace_id, topic_id)
        return [
            ReportExclusion(
                title=item.title,
                url=item.url,
                topic_ids=[],
                reason_code=item.reason_code,
                reason=item.reason,
            )
            for item in library.exclusions
        ]

    async def save_topic_wiki_revision(
        self,
        workspace_id: UUID,
        topic_id: UUID,
        triggering_run_id: UUID,
        markdown: str,
        input_fingerprint: str,
        model_name: str | None,
        prompt_version: str,
        contract_version: str,
        quality_grade: str,
        quality_reasons: list[ReportQualityReason],
        origin: str,
        inputs: list[ReportInput],
        contributions: list[tuple[int, str]],
        exclusions: list[ReportExclusion],
        change_summary: str,
    ) -> tuple[TopicWikiRevision, bool]:
        """Append one wiki revision or return the existing identical snapshot.

        The Topic row is locked while the fingerprint and next revision number
        are decided. That keeps two finishing research questions from replacing
        one another's current wiki pointer.
        """

        pool = await self._connection_pool()
        async with pool.acquire() as connection, connection.transaction():
            topic = await connection.fetchrow(
                """SELECT current_revision_id FROM research_topics
                   WHERE workspace_id = $1 AND id = $2 FOR UPDATE""",
                workspace_id,
                topic_id,
            )
            if topic is None:
                raise KeyError(topic_id)
            existing = await connection.fetchrow(
                """SELECT id, topic_id, revision_number, triggering_run_id,
                          previous_revision_id, markdown, input_fingerprint,
                          quality_grade, quality_reasons, created_at
                   FROM research_topic_wiki_revisions
                   WHERE topic_id = $1 AND input_fingerprint = $2""",
                topic_id,
                input_fingerprint,
            )
            if existing is not None:
                saved = dict(existing)
                saved["quality_reasons"] = _json_value(saved["quality_reasons"], [])
                return TopicWikiRevision(**saved), False
            prior_source_urls: set[str] = set()
            if topic["current_revision_id"] is not None:
                prior_source_urls = set(
                    await connection.fetchval(
                        """SELECT COALESCE(array_agg(source_url), ARRAY[]::TEXT[])
                           FROM research_topic_wiki_revision_inputs
                           WHERE revision_id = $1""",
                        topic["current_revision_id"],
                    )
                    or []
                )
            next_number = await connection.fetchval(
                """SELECT COALESCE(MAX(revision_number), 0) + 1
                   FROM research_topic_wiki_revisions WHERE topic_id = $1""",
                topic_id,
            )
            revision_id = uuid4()
            row = await connection.fetchrow(
                """INSERT INTO research_topic_wiki_revisions
                   (id, topic_id, revision_number, triggering_run_id,
                    previous_revision_id, markdown, input_fingerprint, model_name,
                    prompt_version, contract_version, quality_grade, quality_reasons, origin)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12::jsonb, $13)
                   RETURNING id, topic_id, revision_number, triggering_run_id,
                             previous_revision_id, markdown, input_fingerprint,
                             quality_grade, quality_reasons, created_at""",
                revision_id,
                topic_id,
                next_number,
                triggering_run_id,
                topic["current_revision_id"],
                markdown,
                input_fingerprint,
                model_name,
                prompt_version,
                contract_version,
                quality_grade,
                json.dumps([item.model_dump() for item in quality_reasons]),
                origin,
            )
            if inputs:
                await connection.executemany(
                    """INSERT INTO research_topic_wiki_revision_inputs
                       (revision_id, summary_artifact_id, evidence_id, source_label,
                        source_title, source_url, planned_topic_id, position)
                       SELECT $1, $2, coverage.evidence_id, $3, $4, $5, $6, $7
                       FROM agentic_topic_coverage_evidence AS coverage
                       WHERE coverage.summary_artifact_id = $2
                         AND coverage.source_url = $5
                         AND coverage.content_hash = $8
                       LIMIT 1""",
                    [
                        (
                            revision_id,
                            item.summary_artifact_id,
                            item.source_ref,
                            item.source_title,
                            item.source_url,
                            item.topic_id,
                            item.position,
                            item.content_hash,
                        )
                        for item in inputs
                    ],
                )
            if contributions:
                await connection.executemany(
                    """INSERT INTO research_topic_wiki_contributions
                       (revision_id, finding_position, source_label)
                       VALUES ($1, $2, $3) ON CONFLICT DO NOTHING""",
                    [(revision_id, position, source_ref) for position, source_ref in contributions],
                )
            if exclusions:
                await connection.executemany(
                    """INSERT INTO research_topic_wiki_exclusions
                       (revision_id, source_url, source_title, reason_code, reason)
                       VALUES ($1, $2, $3, $4, $5) ON CONFLICT DO NOTHING""",
                    [
                        (revision_id, item.url, item.title, item.reason_code, item.reason)
                        for item in exclusions
                    ],
                )
            await connection.execute(
                """INSERT INTO research_topic_wiki_updates
                   (revision_id, question, source_additions, source_exclusions,
                    changed_sections, remaining_gaps, change_summary)
                   SELECT $1, run.question, $2::jsonb, $3::jsonb, $4::jsonb, $5::jsonb, $6
                   FROM research_runs AS run WHERE run.id = $7""",
                revision_id,
                json.dumps(
                    [item.source_ref for item in inputs if item.source_url not in prior_source_urls]
                ),
                json.dumps([item.model_dump() for item in exclusions]),
                json.dumps(sorted({item.topic for item in inputs})),
                json.dumps([item.message for item in quality_reasons]),
                change_summary,
                triggering_run_id,
            )
            await connection.execute(
                """UPDATE research_topics SET current_revision_id = $3, updated_at = now()
                   WHERE workspace_id = $1 AND id = $2""",
                workspace_id,
                topic_id,
                revision_id,
            )
        saved = dict(row)
        saved["quality_reasons"] = _json_value(saved["quality_reasons"], [])
        return TopicWikiRevision(**saved), True
    async def save_topic_plan(
        self,
        workspace_id: UUID,
        run_id: UUID,
        plan: TopicPlan,
        prompt_version: str,
    ) -> list[TopicCoverage]:
        """Persist one immutable plan, allowing only exact idempotent replays."""

        pool = await self._connection_pool()
        async with pool.acquire() as connection, connection.transaction():
            owns_run = await connection.fetchval(
                "SELECT 1 FROM research_runs WHERE id = $1 AND workspace_id = $2",
                run_id,
                workspace_id,
            )
            if not owns_run:
                raise KeyError(run_id)
            existing = await connection.fetch(
                """SELECT topic_id, topic, search_query, position, prompt_version
                   FROM agentic_research_topics
                   WHERE workspace_id = $1 AND run_id = $2
                   ORDER BY position""",
                workspace_id,
                run_id,
            )
            requested = [
                {
                    **topic.model_dump(),
                    "position": position,
                    "prompt_version": prompt_version,
                }
                for position, topic in enumerate(plan.root, start=1)
            ]
            if existing:
                stored = [dict(row) for row in existing]
                if stored != requested:
                    raise TopicPlanConflictError(
                        "The research run already has a different immutable topic plan."
                    )
            else:
                await connection.executemany(
                    """INSERT INTO agentic_research_topics
                       (id, workspace_id, run_id, topic_id, topic, search_query,
                        position, prompt_version)
                       VALUES ($1, $2, $3, $4, $5, $6, $7, $8)""",
                    [
                        (
                            uuid4(),
                            workspace_id,
                            run_id,
                            topic.topic_id,
                            topic.topic,
                            topic.search_query,
                            position,
                            prompt_version,
                        )
                        for position, topic in enumerate(plan.root, start=1)
                    ],
                )
        return await self.list_topic_coverage(workspace_id, run_id)

    async def record_discovered_sources(
        self,
        workspace_id: UUID,
        run_id: UUID,
        associations: list[TopicSourceAssociation],
    ) -> None:
        """Persist the topic search that introduced each newly stored source."""

        if not associations:
            return
        pool = await self._connection_pool()
        async with pool.acquire() as connection:
            for association in associations:
                await connection.execute(
                    """INSERT INTO agentic_research_discovered_sources
                       (run_id, topic_record_id, source_url, result_rank)
                       SELECT topic.run_id, topic.id, $4, $5
                       FROM agentic_research_topics AS topic
                       WHERE topic.workspace_id = $1 AND topic.run_id = $2
                         AND topic.topic_id = $3
                       ON CONFLICT (run_id, topic_record_id, source_url) DO NOTHING""",
                    workspace_id,
                    run_id,
                    association.topic_id,
                    association.source_url,
                    association.result_rank,
                )

    async def list_discovered_sources(
        self, workspace_id: UUID, run_id: UUID
    ) -> list[TopicSourceAssociation]:
        pool = await self._connection_pool()
        async with pool.acquire() as connection:
            rows = await connection.fetch(
                """SELECT topic.topic_id, discovered.source_url, discovered.result_rank
                   FROM agentic_research_discovered_sources AS discovered
                   JOIN agentic_research_topics AS topic ON topic.id = discovered.topic_record_id
                   WHERE topic.workspace_id = $1 AND discovered.run_id = $2
                   ORDER BY topic.position, discovered.result_rank""",
                workspace_id,
                run_id,
            )
        return [TopicSourceAssociation(**dict(row)) for row in rows]

    async def report_inputs(self, workspace_id: UUID, run_id: UUID) -> list[ReportInput]:
        """Load the qualified summaries frozen into one report package."""

        pool = await self._connection_pool()
        async with pool.acquire() as connection:
            rows = await connection.fetch(
                """SELECT topic.id AS topic_record_id, topic.topic_id, topic.topic,
                          artifact.id AS summary_artifact_id, coverage.source_url,
                          COALESCE(NULLIF(source.title, ''), coverage.source_url) AS source_title,
                          artifact.summary AS summary_text, coverage.content_hash,
                          row_number() OVER (
                              ORDER BY topic.position, coverage.qualified_at, coverage.source_url
                          )::INTEGER AS position
                   FROM agentic_topic_coverage_evidence AS coverage
                   JOIN agentic_research_topics AS topic ON topic.id = coverage.topic_record_id
                   JOIN evidence_summary_artifacts AS artifact
                     ON artifact.id = coverage.summary_artifact_id
                   LEFT JOIN research_sources AS source
                     ON source.run_id = topic.run_id
                    AND (source.url = coverage.source_url
                         OR source.preflight_final_url = coverage.source_url)
                   WHERE topic.workspace_id = $1 AND topic.run_id = $2
                     AND artifact.evidence_sufficient IS TRUE
                     AND EXISTS (
                         SELECT 1
                         FROM web_evidence_trust_evaluations AS evaluation
                         LEFT JOIN web_evidence_trust_overrides AS active_override
                           ON active_override.evaluation_id = evaluation.id
                          AND active_override.outcome = 'accepted'
                          AND (
                              active_override.expires_at IS NULL
                              OR active_override.expires_at > now()
                          )
                         WHERE evaluation.id = coverage.trust_evaluation_id
                           AND (
                               evaluation.disposition IN ('eligible', 'eligible_with_notice')
                               OR (
                                   evaluation.disposition = 'review_required'
                                   AND active_override.id IS NOT NULL
                               )
                           )
                     )
                   ORDER BY topic.position, coverage.qualified_at, coverage.source_url""",
                workspace_id,
                run_id,
            )
        return [
            ReportInput(
                **dict(row), source_ref=f"S{index:02d}"
            )
            for index, row in enumerate(rows, start=1)
        ]

    async def report_sources(
        self, workspace_id: UUID, run_id: UUID
    ) -> list[ResearchReportSource]:
        """Backward-compatible view of the current qualified report inputs."""

        return [
            ResearchReportSource(
                topic_id=item.topic_id,
                topic=item.topic,
                source_url=item.source_url,
                summary=item.summary_text,
            )
            for item in await self.report_inputs(workspace_id, run_id)
        ]

    async def get_report(
        self, workspace_id: UUID, run_id: UUID
    ) -> ResearchReport | None:
        """Return the newest stored, grounded report without invoking a model."""

        pool = await self._connection_pool()
        async with pool.acquire() as connection:
            row = await connection.fetchrow(
                """SELECT id, run_id, markdown, model_name, prompt_version, contract_version,
                          quality_grade, quality_reasons, report_origin, input_fingerprint,
                          created_at
                   FROM agentic_research_reports
                   WHERE workspace_id = $1 AND run_id = $2
                     AND contract_version IS NOT NULL
                   ORDER BY created_at DESC LIMIT 1""",
                workspace_id,
                run_id,
            )
            if row is None:
                return None
            supporting_rows = await connection.fetch(
                """SELECT source_ref, topic_id, source_title AS title, source_url AS url
                   FROM agentic_research_report_inputs
                   WHERE report_id = $1 ORDER BY position, source_ref""",
                row["id"],
            )
            exclusion_rows = await connection.fetch(
                """SELECT source_title AS title, source_url AS url, topic_ids,
                          reason_code, reason
                   FROM agentic_research_report_exclusions
                   WHERE report_id = $1 ORDER BY source_url, reason_code""",
                row["id"],
            )
            current_inputs = await self.report_inputs(workspace_id, run_id)
        report = dict(row)
        fingerprint = report.pop("input_fingerprint")
        report["quality_reasons"] = _json_value(report["quality_reasons"], [])
        report["supporting_sources"] = [
            ReportSupportingSource(**dict(item)) for item in supporting_rows
        ]
        report["exclusions"] = [
            ReportExclusion(
                **{**dict(item), "topic_ids": _json_value(item["topic_ids"], [])}
            )
            for item in exclusion_rows
        ]
        coverage = await self.list_topic_coverage(workspace_id, run_id)
        report["current"] = fingerprint == _current_report_fingerprint(
            current_inputs, coverage
        )
        return ResearchReport(**report)

    async def report_omissions(self, workspace_id: UUID, run_id: UUID) -> list[str]:
        """Describe summary outcomes omitted from a grounded report without model interpretation."""

        pool = await self._connection_pool()
        async with pool.acquire() as connection:
            rows = await connection.fetch(
                """SELECT sources.url, sources.status, sources.evidence_sufficient,
                          sources.failure_category
                   FROM evidence_summary_execution_sources AS sources
                   JOIN evidence_summary_executions AS execution
                     ON execution.id = sources.execution_id
                   WHERE execution.workspace_id = $1 AND execution.run_id = $2
                     AND execution.created_at = (
                         SELECT MAX(created_at) FROM evidence_summary_executions
                         WHERE workspace_id = $1 AND run_id = $2
                     )
                     AND (sources.status = 'failed' OR sources.evidence_sufficient IS FALSE)
                   ORDER BY sources.url""",
                workspace_id,
                run_id,
            )
        return [
            (
                f"- {row['url']}: {row['failure_category'] or 'evidence_insufficient'}"
            )
            for row in rows
        ]

    async def report_exclusions(
        self, workspace_id: UUID, run_id: UUID, inputs: list[ReportInput]
    ) -> list[ReportExclusion]:
        """Describe known noncontributing sources without changing their eligibility."""

        included_urls = {item.source_url for item in inputs}
        topics = await self.list_topic_coverage(workspace_id, run_id)
        topic_ids = [item.topic_id for item in topics]
        pool = await self._connection_pool()
        async with pool.acquire() as connection:
            rows = await connection.fetch(
                """SELECT source.title, source.url,
                          COALESCE(source.preflight_final_url, source.url) AS evidence_url,
                          source.preflight_status,
                          source.preflight_reason,
                          source.preflight_trust_disposition,
                          execution_source.status AS summary_status,
                          execution_source.evidence_sufficient,
                          execution_source.failure_category
                   FROM research_sources AS source
                   JOIN research_runs AS run ON run.id = source.run_id
                   LEFT JOIN LATERAL (
                       SELECT member.status, member.evidence_sufficient, member.failure_category
                       FROM evidence_summary_execution_sources AS member
                       JOIN evidence_summary_executions AS execution
                         ON execution.id = member.execution_id
                       WHERE execution.workspace_id = $1 AND execution.run_id = source.run_id
                         AND member.url = COALESCE(source.preflight_final_url, source.url)
                       ORDER BY execution.created_at DESC LIMIT 1
                   ) AS execution_source ON TRUE
                   WHERE run.workspace_id = $1 AND source.run_id = $2
                   ORDER BY source.rank""",
                workspace_id,
                run_id,
            )
        exclusions: list[ReportExclusion] = []
        for row in rows:
            source_url = row["evidence_url"]
            if source_url in included_urls:
                continue
            code, reason = _report_exclusion_reason(row)
            exclusions.append(
                ReportExclusion(
                    title=row["title"] or source_url,
                    url=source_url,
                    topic_ids=topic_ids,
                    reason_code=code,
                    reason=reason,
                )
            )
        return exclusions

    async def save_report_package(
        self,
        workspace_id: UUID,
        run_id: UUID,
        markdown: str,
        model_name: str | None,
        prompt_version: str,
        contract_version: str,
        input_fingerprint: str,
        quality_grade: str,
        quality_reasons: list[ReportQualityReason],
        report_origin: str,
        inputs: list[ReportInput],
        contributions: list[tuple[UUID, int, str, str]],
        exclusions: list[ReportExclusion],
        attempts: list[FinalReportAttempt],
    ) -> ResearchReport:
        pool = await self._connection_pool()
        report_id = uuid4()
        async with pool.acquire() as connection, connection.transaction():
            row = await connection.fetchrow(
                """INSERT INTO agentic_research_reports
                   (id, workspace_id, run_id, markdown, model_name, prompt_version,
                    contract_version, input_fingerprint, quality_grade, quality_reasons,
                    report_origin)
                   SELECT $3, runs.workspace_id, runs.id, $4, $5, $6, $7, $8, $9,
                          $10::jsonb, $11
                   FROM research_runs AS runs
                   WHERE runs.workspace_id = $1 AND runs.id = $2
                   RETURNING id, run_id, markdown, model_name, prompt_version, contract_version,
                             quality_grade, quality_reasons, report_origin, created_at""",
                workspace_id,
                run_id,
                report_id,
                markdown,
                model_name,
                prompt_version,
                contract_version,
                input_fingerprint,
                quality_grade,
                json.dumps([item.model_dump() for item in quality_reasons]),
                report_origin,
            )
            if row is None:
                raise KeyError(run_id)
            await connection.executemany(
                """INSERT INTO agentic_research_report_inputs
                   (report_id, topic_record_id, topic_id, topic, summary_artifact_id,
                    source_ref, source_url, source_title, summary_text, summary_digest,
                    content_hash, position)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)""",
                [
                    (
                        report_id, item.topic_record_id, item.topic_id, item.topic,
                        item.summary_artifact_id, item.source_ref, item.source_url,
                        item.source_title, item.summary_text, _summary_digest(item.summary_text),
                        item.content_hash, item.position,
                    )
                    for item in inputs
                ],
            )
            if contributions:
                await connection.executemany(
                    """INSERT INTO agentic_research_report_contributions
                       (report_id, topic_record_id, finding_position, source_ref,
                        contribution_kind)
                       VALUES ($1, $2, $3, $4, $5)""",
                    [(report_id, *item) for item in contributions],
                )
            if exclusions:
                await connection.executemany(
                    """INSERT INTO agentic_research_report_exclusions
                       (report_id, source_url, source_title, topic_ids, reason_code, reason)
                       VALUES ($1, $2, $3, $4::jsonb, $5, $6)""",
                    [
                        (report_id, item.url, item.title, json.dumps(item.topic_ids),
                         item.reason_code, item.reason)
                        for item in exclusions
                    ],
                )
            if attempts:
                await connection.executemany(
                    """INSERT INTO agentic_research_report_attempts
                       (id, report_id, topic_id, group_index, attempt_number, status,
                        input_fingerprint,
                        model_name, prompt_version, contract_version, raw_response,
                        validation_errors, duration_ms, input_characters,
                        response_characters, failure_code)
                       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                               $11, $12::jsonb, $13, $14, $15, $16)""",
                    [
                        (uuid4(), report_id, item.topic_id, item.group_index,
                         item.attempt_number, item.status, input_fingerprint,
                         item.model_name, item.prompt_version, contract_version,
                         item.raw_response, json.dumps(item.validation_errors),
                         item.duration_ms, item.input_characters,
                         item.response_characters, item.failure_code)
                        for item in attempts
                    ],
                )
        saved = dict(row)
        saved["quality_reasons"] = _json_value(saved["quality_reasons"], [])
        return ResearchReport(
            **saved,
            supporting_sources=[
                ReportSupportingSource(
                    source_ref=item.source_ref, topic_id=item.topic_id,
                    title=item.source_title, url=item.source_url
                )
                for item in inputs
            ],
            exclusions=exclusions,
        )

    async def record_relevance_decision(
        self,
        workspace_id: UUID,
        run_id: UUID,
        topic_id: str,
        source_url: str,
        content_hash: str,
        decision: RelevanceDecision,
        model_name: str,
        prompt_version: str,
        model_output: str,
        failure_reason: str | None = None,
    ) -> TopicRelevanceRecord:
        """Store one validated relevance outcome for an exact topic and evidence version."""

        pool = await self._connection_pool()
        async with pool.acquire() as connection:
            row = await connection.fetchrow(
                """INSERT INTO agentic_topic_relevance_decisions
                   (id, topic_record_id, source_url, content_hash, decision,
                    model_name, prompt_version, model_output, failure_reason)
                   SELECT $6, topic.id, $4, $5, $7, $8, $9, $10, $11
                   FROM agentic_research_topics AS topic
                   WHERE topic.workspace_id = $1 AND topic.run_id = $2
                     AND topic.topic_id = $3
                   RETURNING *""",
                workspace_id,
                run_id,
                topic_id,
                source_url,
                content_hash,
                uuid4(),
                decision,
                model_name,
                prompt_version,
                model_output,
                failure_reason,
            )
        if row is None:
            raise KeyError(topic_id)
        return TopicRelevanceRecord(**dict(row))

    async def relevance_input(
        self,
        workspace_id: UUID,
        run_id: UUID,
        topic_id: str,
        source_url: str,
        content_hash: str,
    ) -> TopicRelevanceInput | None:
        """Return exact evidence only when its latest trust decision permits model use."""

        pool = await self._connection_pool()
        async with pool.acquire() as connection:
            row = await connection.fetchrow(
                """SELECT run.question AS operator_question, topic.topic_id, topic.topic,
                          evidence.url AS source_url, evidence.content_hash,
                          evidence.text AS evidence_text
                   FROM agentic_research_topics AS topic
                   JOIN research_runs AS run
                     ON run.id = topic.run_id AND run.workspace_id = topic.workspace_id
                   JOIN LATERAL (
                       SELECT stored.url, stored.content_hash, stored.text
                       FROM research_evidence AS stored
                       JOIN research_runs AS evidence_run ON evidence_run.id = stored.run_id
                       WHERE evidence_run.workspace_id = topic.workspace_id
                         AND stored.url = $4 AND stored.content_hash = $5
                         AND length(btrim(stored.text)) > 0
                       ORDER BY stored.retrieved_at DESC
                       LIMIT 1
                   ) AS evidence ON TRUE
                   JOIN LATERAL (
                       SELECT evaluation.disposition,
                              active_override.id AS override_id,
                              active_override.outcome AS override_outcome
                       FROM web_evidence_trust_evaluations AS evaluation
                       LEFT JOIN LATERAL (
                           SELECT override.id, override.outcome
                           FROM web_evidence_trust_overrides AS override
                           WHERE override.evaluation_id = evaluation.id
                             AND (
                                 override.expires_at IS NULL
                                 OR override.expires_at > now()
                             )
                           ORDER BY override.created_at DESC
                           LIMIT 1
                       ) AS active_override ON TRUE
                       WHERE evaluation.workspace_id = topic.workspace_id
                         AND evaluation.source_url = evidence.url
                         AND evaluation.content_hash = evidence.content_hash
                       ORDER BY evaluation.created_at DESC
                       LIMIT 1
                   ) AS trust ON (
                       trust.disposition IN ('eligible', 'eligible_with_notice')
                       OR (
                           trust.disposition = 'review_required'
                           AND trust.override_id IS NOT NULL
                           AND trust.override_outcome = 'accepted'
                       )
                   )
                   WHERE topic.workspace_id = $1 AND topic.run_id = $2
                     AND topic.topic_id = $3""",
                workspace_id,
                run_id,
                topic_id,
                source_url,
                content_hash,
            )
        return TopicRelevanceInput(**dict(row)) if row is not None else None

    async def qualify_evidence(
        self,
        workspace_id: UUID,
        run_id: UUID,
        topic_id: str,
        source_url: str,
        content_hash: str,
    ) -> TopicCoverageAssessment:
        """Store coverage only when all four canonical records currently qualify."""

        pool = await self._connection_pool()
        async with pool.acquire() as connection, connection.transaction():
            row = await connection.fetchrow(
                _COVERAGE_FACTS_QUERY,
                workspace_id,
                run_id,
                topic_id,
                source_url,
                content_hash,
            )
            facts = TopicCoverageFacts(**dict(row)) if row is not None else TopicCoverageFacts()
            assessment = assess_topic_coverage(facts)
            if not assessment.counts_toward_topic:
                return assessment
            await connection.execute(
                """INSERT INTO agentic_topic_coverage_evidence
                   (id, topic_record_id, source_url, content_hash, evidence_id,
                    trust_evaluation_id, relevance_decision_id, summary_artifact_id)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                   ON CONFLICT (topic_record_id, source_url, content_hash) DO UPDATE
                   SET evidence_id = EXCLUDED.evidence_id,
                       trust_evaluation_id = EXCLUDED.trust_evaluation_id,
                       relevance_decision_id = EXCLUDED.relevance_decision_id,
                       summary_artifact_id = EXCLUDED.summary_artifact_id,
                       qualified_at = now()""",
                uuid4(),
                facts.topic_record_id,
                source_url,
                content_hash,
                facts.evidence_id,
                facts.trust_evaluation_id,
                facts.relevance_decision_id,
                facts.summary_artifact_id,
            )
        return assessment

    async def list_topic_coverage(
        self, workspace_id: UUID, run_id: UUID
    ) -> list[TopicCoverage]:
        """Return topics and their qualifying sources without reading source keywords."""

        pool = await self._connection_pool()
        async with pool.acquire() as connection:
            rows = await connection.fetch(
                """SELECT topic.topic_id, topic.topic, topic.search_query,
                          coverage.source_url, coverage.content_hash, coverage.evidence_id,
                          coverage.trust_evaluation_id, coverage.relevance_decision_id,
                          coverage.summary_artifact_id, coverage.qualified_at
                   FROM agentic_research_topics AS topic
                   LEFT JOIN agentic_topic_coverage_evidence AS coverage
                     ON coverage.topic_record_id = topic.id
                    AND coverage.relevance_decision_id = (
                        SELECT latest_relevance.id
                        FROM agentic_topic_relevance_decisions AS latest_relevance
                        WHERE latest_relevance.topic_record_id = topic.id
                          AND latest_relevance.source_url = coverage.source_url
                          AND latest_relevance.content_hash = coverage.content_hash
                        ORDER BY latest_relevance.created_at DESC
                        LIMIT 1
                    )
                    AND coverage.trust_evaluation_id = (
                        SELECT latest_evaluation.id
                        FROM web_evidence_trust_evaluations AS latest_evaluation
                        WHERE latest_evaluation.workspace_id = topic.workspace_id
                          AND latest_evaluation.source_url = coverage.source_url
                          AND latest_evaluation.content_hash = coverage.content_hash
                        ORDER BY latest_evaluation.created_at DESC
                        LIMIT 1
                    )
                    AND EXISTS (
                        SELECT 1
                        FROM web_evidence_trust_evaluations AS effective_evaluation
                        LEFT JOIN web_evidence_trust_overrides AS active_override
                          ON active_override.evaluation_id = effective_evaluation.id
                         AND active_override.outcome = 'accepted'
                         AND (
                             active_override.expires_at IS NULL
                             OR active_override.expires_at > now()
                         )
                        WHERE effective_evaluation.id = coverage.trust_evaluation_id
                          AND (
                              effective_evaluation.disposition IN (
                                  'eligible', 'eligible_with_notice'
                              )
                              OR (
                                  effective_evaluation.disposition = 'review_required'
                                  AND active_override.id IS NOT NULL
                              )
                          )
                    )
                   WHERE topic.workspace_id = $1 AND topic.run_id = $2
                   ORDER BY topic.position, coverage.qualified_at""",
                workspace_id,
                run_id,
            )
        return self._coverage_contracts(rows)

    @staticmethod
    def _coverage_contracts(rows: list[Mapping[str, object]]) -> list[TopicCoverage]:
        topics: dict[str, TopicCoverage] = {}
        for row in rows:
            topic_id = str(row["topic_id"])
            coverage = topics.setdefault(
                topic_id,
                TopicCoverage(
                    topic_id=topic_id,
                    topic=str(row["topic"]),
                    search_query=str(row["search_query"]),
                    status="uncovered",
                ),
            )
            if row["source_url"] is not None:
                coverage.evidence.append(
                    TopicCoverageEvidence(
                        source_url=str(row["source_url"]),
                        content_hash=str(row["content_hash"]),
                        evidence_id=row["evidence_id"],
                        trust_evaluation_id=row["trust_evaluation_id"],
                        relevance_decision_id=row["relevance_decision_id"],
                        summary_artifact_id=row["summary_artifact_id"],
                        qualified_at=row["qualified_at"],
                    )
                )
                coverage.status = "covered"
        return list(topics.values())
