"""Canonical, workspace-scoped request records; no provider access."""

from uuid import UUID, uuid4

import asyncpg

from app.evidence_summaries.contracts import EvidenceSummaryBatch, EvidenceSummarySource
from evidence_intelligence.contracts import PreparedBatch
from evidence_intelligence.routing import ExecutionRoute

SCHEMA = """
CREATE TABLE IF NOT EXISTS evidence_summary_batches (
 id UUID PRIMARY KEY, workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
 run_id UUID NOT NULL REFERENCES research_runs(id) ON DELETE CASCADE,
 route TEXT NOT NULL CHECK (route IN ('direct','durable')),
 status TEXT NOT NULL CHECK (status IN ('pending')) DEFAULT 'pending',
 created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS evidence_summary_sources (
 batch_id UUID NOT NULL REFERENCES evidence_summary_batches(id) ON DELETE CASCADE,
 content_hash TEXT NOT NULL, url TEXT NOT NULL, chunk_count INTEGER NOT NULL CHECK (chunk_count > 0),
 status TEXT NOT NULL CHECK (status IN ('pending')) DEFAULT 'pending', PRIMARY KEY (batch_id, content_hash)
);
"""

class EvidenceSummaryStoreUnavailable(RuntimeError): pass

class EvidenceSummaryStore:
 def __init__(self, database_url: str | None): self.database_url, self.pool = database_url, None
 async def _pool(self):
  if not self.database_url: raise EvidenceSummaryStoreUnavailable("Summary persistence is not configured.")
  if self.pool is None:
   try:
    self.pool = await asyncpg.create_pool(self.database_url, min_size=1, max_size=5)
    async with self.pool.acquire() as c: await c.execute(SCHEMA)
   except (asyncpg.PostgresError, OSError) as e: raise EvidenceSummaryStoreUnavailable("Summary persistence is unavailable.") from e
  return self.pool
 async def create(self, workspace_id: UUID, run_id: UUID, prepared: PreparedBatch, route: ExecutionRoute) -> EvidenceSummaryBatch:
  pool = await self._pool(); batch_id = uuid4()
  async with pool.acquire() as c, c.transaction():
   row = await c.fetchrow("INSERT INTO evidence_summary_batches (id,workspace_id,run_id,route) VALUES ($1,$2,$3,$4) RETURNING id,workspace_id,run_id,route,status,created_at", batch_id, workspace_id, run_id, str(route))
   for source in prepared.sources:
    await c.execute("INSERT INTO evidence_summary_sources (batch_id,content_hash,url,chunk_count) VALUES ($1,$2,$3,$4)", batch_id, source.content_hash, source.source_url, len(source.chunks))
  return EvidenceSummaryBatch(**dict(row), sources=[EvidenceSummarySource(content_hash=s.content_hash,url=s.source_url,chunk_count=len(s.chunks)) for s in prepared.sources])
