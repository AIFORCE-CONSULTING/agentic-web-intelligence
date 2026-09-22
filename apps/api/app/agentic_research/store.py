"""Postgres records for research topics, relevance, and evidence coverage."""

from collections.abc import Mapping
from uuid import UUID, uuid4

import asyncpg

from app.agentic_research.contracts import (
    RelevanceDecision,
    TopicCoverage,
    TopicCoverageAssessment,
    TopicCoverageEvidence,
    TopicCoverageFacts,
    TopicPlan,
    TopicRelevanceRecord,
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
CREATE INDEX IF NOT EXISTS agentic_research_topics_workspace_run_idx
    ON agentic_research_topics(workspace_id, run_id, created_at);
CREATE INDEX IF NOT EXISTS agentic_topic_relevance_lookup_idx
    ON agentic_topic_relevance_decisions(
        topic_record_id, source_url, content_hash, created_at DESC
    );
CREATE INDEX IF NOT EXISTS agentic_topic_coverage_lookup_idx
    ON agentic_topic_coverage_evidence(topic_record_id, qualified_at);
"""


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
                      active_override.id AS override_id
               FROM web_evidence_trust_evaluations AS evaluation
               LEFT JOIN LATERAL (
                   SELECT override.id
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
                async with self._pool.acquire() as connection:
                    await connection.execute(SCHEMA)
            except (asyncpg.PostgresError, OSError) as error:
                if self._pool is not None:
                    await self._pool.close()
                    self._pool = None
                raise AgenticResearchStoreUnavailable(
                    "Agentic research persistence is unavailable."
                ) from error
        return self._pool

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
    ) -> TopicRelevanceRecord:
        """Store one validated relevance outcome for an exact topic and evidence version."""

        pool = await self._connection_pool()
        async with pool.acquire() as connection:
            row = await connection.fetchrow(
                """INSERT INTO agentic_topic_relevance_decisions
                   (id, topic_record_id, source_url, content_hash, decision,
                    model_name, prompt_version)
                   SELECT $6, topic.id, $4, $5, $7, $8, $9
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
            )
        if row is None:
            raise KeyError(topic_id)
        return TopicRelevanceRecord(**dict(row))

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
