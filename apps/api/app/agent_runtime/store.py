"""Postgres persistence and server-side guards for the Phase 3 runtime core."""

import json
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import asyncpg

from app.agent_runtime.contracts import (
    ApprovedPlanStep,
    RuntimeEvent,
    RuntimeHandoff,
    RuntimeMemory,
    RuntimeRun,
    RuntimeRunSummary,
    RuntimeStep,
    RuntimeStoreUnavailable,
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS agent_runtime_runs (
    id UUID PRIMARY KEY,
    goal TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN (
        'requested', 'planning', 'awaiting_approval', 'executing', 'reviewing',
        'completed', 'rejected', 'failed', 'cancelled', 'needs_attention'
    )),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS agent_runtime_steps (
    id UUID PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES agent_runtime_runs(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('orchestrator', 'planner', 'researcher', 'reviewer')),
    title TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending', 'active', 'completed', 'failed', 'cancelled', 'needs_attention')),
    allowed_capabilities JSONB NOT NULL DEFAULT '[]'::jsonb,
    attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    idempotency_key TEXT NOT NULL,
    timeout_seconds INTEGER NOT NULL CHECK (timeout_seconds > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS agent_runtime_handoffs (
    id UUID PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES agent_runtime_runs(id) ON DELETE CASCADE,
    sender_step_id UUID NOT NULL REFERENCES agent_runtime_steps(id) ON DELETE RESTRICT,
    recipient_step_id UUID NOT NULL REFERENCES agent_runtime_steps(id) ON DELETE RESTRICT,
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS agent_runtime_events (
    id UUID PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES agent_runtime_runs(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    details JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE TABLE IF NOT EXISTS agent_runtime_memories (
    id UUID PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES agent_runtime_runs(id) ON DELETE CASCADE,
    memory_type TEXT NOT NULL CHECK (memory_type IN ('research_query', 'source_reference')),
    content JSONB NOT NULL,
    source_step_id UUID REFERENCES agent_runtime_steps(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS agent_runtime_runs_updated_at_idx
    ON agent_runtime_runs(updated_at DESC);
CREATE INDEX IF NOT EXISTS agent_runtime_steps_run_id_idx
    ON agent_runtime_steps(run_id, created_at);
CREATE INDEX IF NOT EXISTS agent_runtime_handoffs_run_id_idx
    ON agent_runtime_handoffs(run_id, created_at);
CREATE INDEX IF NOT EXISTS agent_runtime_events_run_id_idx
    ON agent_runtime_events(run_id, occurred_at);
CREATE INDEX IF NOT EXISTS agent_runtime_memories_run_id_idx
    ON agent_runtime_memories(run_id, expires_at);
"""

RUN_MEMORY_RETENTION = timedelta(hours=24)

ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "requested": frozenset({"planning", "cancelled"}),
    "planning": frozenset({"awaiting_approval", "rejected", "failed", "cancelled"}),
    "awaiting_approval": frozenset({"executing", "rejected", "cancelled"}),
    "executing": frozenset({"reviewing", "failed", "cancelled", "needs_attention"}),
    "reviewing": frozenset({"completed", "needs_attention", "failed", "cancelled"}),
    "completed": frozenset(),
    "rejected": frozenset(),
    "failed": frozenset(),
    "cancelled": frozenset(),
    "needs_attention": frozenset(),
}


class RuntimeTransitionError(ValueError):
    """Raised when a requested lifecycle transition is not valid."""


class RuntimeHandoffError(ValueError):
    """Raised when a handoff cannot be matched to server-owned plan state."""


class RuntimeStore:
    """Lazy durable store; agents have no mutation path to role or capability fields."""

    def __init__(self, database_url: str | None) -> None:
        self._database_url = database_url
        self._pool: asyncpg.Pool | None = None

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    async def _connection_pool(self) -> asyncpg.Pool:
        if not self._database_url:
            raise RuntimeStoreUnavailable("Agent runtime persistence is not configured.")
        if self._pool is None:
            try:
                self._pool = await asyncpg.create_pool(self._database_url, min_size=1, max_size=5)
                async with self._pool.acquire() as connection:
                    await connection.execute(SCHEMA)
            except (asyncpg.PostgresError, OSError) as error:
                if self._pool is not None:
                    await self._pool.close()
                    self._pool = None
                raise RuntimeStoreUnavailable("Agent runtime persistence is unavailable.") from error
        return self._pool

    async def create_run(self, goal: str) -> RuntimeRun:
        """Create a requested run and its fixed, server-assigned planner step."""

        pool = await self._connection_pool()
        run_id = uuid4()
        planner_step_id = uuid4()
        async with pool.acquire() as connection, connection.transaction():
            await connection.execute(
                "INSERT INTO agent_runtime_runs (id, goal, status) VALUES ($1, $2, 'requested')",
                run_id,
                goal,
            )
            await connection.execute(
                """INSERT INTO agent_runtime_steps
                (id, run_id, role, title, status, allowed_capabilities, idempotency_key, timeout_seconds)
                VALUES ($1, $2, 'planner', 'Create a bounded plan', 'pending', '[]'::jsonb, $3, 60)""",
                planner_step_id,
                run_id,
                f"planner:{planner_step_id}",
            )
            await self._append_event(
                connection,
                run_id,
                "runtime.run.requested",
                {"planner_step_id": str(planner_step_id)},
            )
        run = await self.get_run(run_id)
        assert run is not None
        return run

    async def transition_run(self, run_id: UUID, next_status: str) -> RuntimeRun | None:
        """Perform a server-validated state transition and append its audit event."""

        pool = await self._connection_pool()
        async with pool.acquire() as connection, connection.transaction():
            current = await connection.fetchval(
                "SELECT status FROM agent_runtime_runs WHERE id = $1 FOR UPDATE", run_id
            )
            if current is None:
                return None
            if next_status not in ALLOWED_TRANSITIONS[current]:
                raise RuntimeTransitionError(f"Cannot transition runtime run from {current} to {next_status}.")
            await connection.execute(
                "UPDATE agent_runtime_runs SET status = $2, updated_at = now() WHERE id = $1",
                run_id,
                next_status,
            )
            await self._append_event(
                connection,
                run_id,
                "runtime.run.transitioned",
                {"from_status": current, "to_status": next_status},
            )
        return await self.get_run(run_id)

    async def materialize_plan(
        self, run_id: UUID, assignments: list[ApprovedPlanStep]
    ) -> RuntimeRun | None:
        """Persist a validated plan and advance it to the approval gate atomically."""

        pool = await self._connection_pool()
        async with pool.acquire() as connection, connection.transaction():
            current = await connection.fetchval(
                "SELECT status FROM agent_runtime_runs WHERE id = $1 FOR UPDATE", run_id
            )
            if current is None:
                return None
            if current != "planning":
                raise RuntimeTransitionError(
                    f"Cannot materialize a plan while runtime run status is {current}."
                )
            planner_step_id = await connection.fetchval(
                """SELECT id FROM agent_runtime_steps
                WHERE run_id = $1 AND role = 'planner' ORDER BY created_at LIMIT 1 FOR UPDATE""",
                run_id,
            )
            if planner_step_id is None:
                raise RuntimeTransitionError("Runtime run has no server-assigned planner step.")
            await connection.execute(
                """UPDATE agent_runtime_steps
                SET status = 'completed', updated_at = now() WHERE id = $1""",
                planner_step_id,
            )
            for assignment in assignments:
                await connection.execute(
                    """INSERT INTO agent_runtime_steps
                    (id, run_id, role, title, status, allowed_capabilities, idempotency_key, timeout_seconds)
                    VALUES ($1, $2, $3, $4, 'pending', $5::jsonb, $6, $7)""",
                    assignment.id,
                    run_id,
                    assignment.role,
                    assignment.title,
                    json.dumps(assignment.allowed_capabilities),
                    assignment.idempotency_key,
                    assignment.timeout_seconds,
                )
            await connection.execute(
                """UPDATE agent_runtime_runs
                SET status = 'awaiting_approval', updated_at = now() WHERE id = $1""",
                run_id,
            )
            await self._append_event(
                connection,
                run_id,
                "runtime.plan.materialized",
                {
                    "planner_step_id": str(planner_step_id),
                    "step_ids": [str(assignment.id) for assignment in assignments],
                },
            )
        return await self.get_run(run_id)

    async def create_handoff(
        self, run_id: UUID, sender_step_id: UUID, recipient_step_id: UUID, content: str
    ) -> RuntimeHandoff:
        """Create a handoff only between plan steps in the same server-owned run."""

        pool = await self._connection_pool()
        handoff_id = uuid4()
        async with pool.acquire() as connection, connection.transaction():
            run_status = await connection.fetchval(
                "SELECT status FROM agent_runtime_runs WHERE id = $1 FOR UPDATE", run_id
            )
            if run_status is None:
                raise RuntimeHandoffError("Runtime run was not found.")
            if run_status not in {"planning", "executing", "reviewing"}:
                raise RuntimeHandoffError("Runtime run is not accepting handoffs in its current state.")
            steps = await connection.fetch(
                "SELECT id, role FROM agent_runtime_steps WHERE run_id = $1 AND id = ANY($2::uuid[])",
                run_id,
                [sender_step_id, recipient_step_id],
            )
            if len(steps) != 2:
                raise RuntimeHandoffError("Handoff steps must belong to the same runtime run.")
            await connection.execute(
                """INSERT INTO agent_runtime_handoffs
                (id, run_id, sender_step_id, recipient_step_id, content)
                VALUES ($1, $2, $3, $4, $5)""",
                handoff_id,
                run_id,
                sender_step_id,
                recipient_step_id,
                content,
            )
            await self._append_event(
                connection,
                run_id,
                "runtime.handoff.created",
                {"sender_step_id": str(sender_step_id), "recipient_step_id": str(recipient_step_id)},
            )
            row = await connection.fetchrow(
                "SELECT id, sender_step_id, recipient_step_id, content, created_at "
                "FROM agent_runtime_handoffs WHERE id = $1",
                handoff_id,
            )
        assert row is not None
        return self._handoff_from_row(row)

    async def activate_step(self, run_id: UUID, step_id: UUID) -> None:
        """Activate one pending step only while its run is executing."""

        pool = await self._connection_pool()
        async with pool.acquire() as connection, connection.transaction():
            run_status = await connection.fetchval(
                "SELECT status FROM agent_runtime_runs WHERE id = $1 FOR UPDATE", run_id
            )
            if run_status != "executing":
                raise RuntimeTransitionError("Runtime run is not executing.")
            updated = await connection.execute(
                """UPDATE agent_runtime_steps
                SET status = 'active', attempt_count = attempt_count + 1, updated_at = now()
                WHERE id = $1 AND run_id = $2 AND status = 'pending'""",
                step_id,
                run_id,
            )
            if updated != "UPDATE 1":
                raise RuntimeTransitionError("Runtime step is not pending in this run.")
            await self._append_event(
                connection, run_id, "runtime.step.activated", {"step_id": str(step_id)}
            )

    async def complete_step(self, run_id: UUID, step_id: UUID) -> None:
        """Complete one active step and retain its immutable authority record."""

        pool = await self._connection_pool()
        async with pool.acquire() as connection, connection.transaction():
            updated = await connection.execute(
                """UPDATE agent_runtime_steps
                SET status = 'completed', updated_at = now()
                WHERE id = $1 AND run_id = $2 AND status = 'active'""",
                step_id,
                run_id,
            )
            if updated != "UPDATE 1":
                raise RuntimeTransitionError("Runtime step is not active in this run.")
            await self._append_event(
                connection, run_id, "runtime.step.completed", {"step_id": str(step_id)}
            )

    async def fail_step(self, run_id: UUID, step_id: UUID, reason: str) -> None:
        """Record a bounded failure before the service moves the run to a terminal state."""

        pool = await self._connection_pool()
        async with pool.acquire() as connection, connection.transaction():
            await connection.execute(
                """UPDATE agent_runtime_steps
                SET status = 'failed', updated_at = now()
                WHERE id = $1 AND run_id = $2 AND status = 'active'""",
                step_id,
                run_id,
            )
            await self._append_event(
                connection,
                run_id,
                "runtime.step.failed",
                {"step_id": str(step_id), "reason": reason[:512]},
            )

    async def record_event(self, run_id: UUID, event_type: str, details: dict[str, object]) -> None:
        """Append one sanitized runtime event from trusted orchestration code."""

        pool = await self._connection_pool()
        async with pool.acquire() as connection:
            await self._append_event(connection, run_id, event_type, details)

    async def record_memory(
        self,
        run_id: UUID,
        memory_type: str,
        content: dict[str, object],
        source_step_id: UUID | None = None,
    ) -> RuntimeMemory:
        """Persist one bounded run-owned memory with a fixed retention deadline."""

        pool = await self._connection_pool()
        memory_id = uuid4()
        expires_at = datetime.now(UTC) + RUN_MEMORY_RETENTION
        async with pool.acquire() as connection, connection.transaction():
            exists = await connection.fetchval(
                "SELECT EXISTS(SELECT 1 FROM agent_runtime_runs WHERE id = $1)", run_id
            )
            if not exists:
                raise RuntimeTransitionError("Runtime run was not found.")
            row = await connection.fetchrow(
                """INSERT INTO agent_runtime_memories
                (id, run_id, memory_type, content, source_step_id, expires_at)
                VALUES ($1, $2, $3, $4::jsonb, $5, $6)
                RETURNING id, run_id, memory_type, content, source_step_id, created_at, expires_at""",
                memory_id,
                run_id,
                memory_type,
                json.dumps(content),
                source_step_id,
                expires_at,
            )
            assert row is not None
            await self._append_event(
                connection,
                run_id,
                "runtime.memory.recorded",
                {"memory_id": str(memory_id), "memory_type": memory_type},
            )
        return self._memory_from_row(row)

    async def get_run(self, run_id: UUID) -> RuntimeRun | None:
        pool = await self._connection_pool()
        async with pool.acquire() as connection:
            run = await connection.fetchrow("SELECT * FROM agent_runtime_runs WHERE id = $1", run_id)
            if run is None:
                return None
            steps = await connection.fetch(
                "SELECT * FROM agent_runtime_steps WHERE run_id = $1 ORDER BY created_at", run_id
            )
            handoffs = await connection.fetch(
                "SELECT * FROM agent_runtime_handoffs WHERE run_id = $1 ORDER BY created_at", run_id
            )
            memories = await connection.fetch(
                """SELECT id, run_id, memory_type, content, source_step_id, created_at, expires_at
                FROM agent_runtime_memories WHERE run_id = $1 AND expires_at > now()
                ORDER BY created_at""",
                run_id,
            )
            events = await connection.fetch(
                "SELECT event_type, occurred_at, details FROM agent_runtime_events "
                "WHERE run_id = $1 ORDER BY occurred_at",
                run_id,
            )
        return RuntimeRun(
            id=run["id"], goal=run["goal"], status=run["status"], created_at=run["created_at"],
            updated_at=run["updated_at"], steps=[self._step_from_row(row) for row in steps],
            handoffs=[self._handoff_from_row(row) for row in handoffs],
            memories=[self._memory_from_row(row) for row in memories],
            events=[self._event_from_row(row) for row in events],
        )

    async def list_runs(self, limit: int) -> list[RuntimeRunSummary]:
        pool = await self._connection_pool()
        async with pool.acquire() as connection:
            rows = await connection.fetch(
                """SELECT runs.*, COUNT(steps.id)::integer AS step_count
                FROM agent_runtime_runs AS runs
                LEFT JOIN agent_runtime_steps AS steps ON steps.run_id = runs.id
                GROUP BY runs.id ORDER BY runs.updated_at DESC LIMIT $1""",
                limit,
            )
        return [RuntimeRunSummary(**dict(row)) for row in rows]

    @staticmethod
    async def _append_event(
        connection: asyncpg.Connection, run_id: UUID, event_type: str, details: dict[str, object]
    ) -> None:
        await connection.execute(
            "INSERT INTO agent_runtime_events (id, run_id, event_type, details) VALUES ($1, $2, $3, $4::jsonb)",
            uuid4(), run_id, event_type, json.dumps(details),
        )

    @staticmethod
    def _step_from_row(row: asyncpg.Record) -> RuntimeStep:
        capabilities = row["allowed_capabilities"]
        if isinstance(capabilities, str):
            capabilities = json.loads(capabilities)
        return RuntimeStep(
            id=row["id"], role=row["role"], title=row["title"], status=row["status"],
            allowed_capabilities=capabilities,
            attempt_count=row["attempt_count"], idempotency_key=row["idempotency_key"],
            timeout_seconds=row["timeout_seconds"], created_at=row["created_at"], updated_at=row["updated_at"],
        )

    @staticmethod
    def _handoff_from_row(row: asyncpg.Record) -> RuntimeHandoff:
        return RuntimeHandoff(
            id=row["id"], sender_step_id=row["sender_step_id"],
            recipient_step_id=row["recipient_step_id"], content=row["content"], created_at=row["created_at"],
        )

    @staticmethod
    def _event_from_row(row: asyncpg.Record) -> RuntimeEvent:
        details = row["details"]
        if isinstance(details, str):
            details = json.loads(details)
        return RuntimeEvent(event_type=row["event_type"], occurred_at=row["occurred_at"], details=details)

    @staticmethod
    def _memory_from_row(row: asyncpg.Record) -> RuntimeMemory:
        content = row["content"]
        if isinstance(content, str):
            content = json.loads(content)
        return RuntimeMemory(
            id=row["id"],
            run_id=row["run_id"],
            memory_type=row["memory_type"],
            content=content,
            source_step_id=row["source_step_id"],
            created_at=row["created_at"],
            expires_at=row["expires_at"],
        )
