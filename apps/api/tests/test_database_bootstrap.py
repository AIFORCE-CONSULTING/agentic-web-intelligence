import asyncio
import inspect
from pathlib import Path

import pytest

from app import database_bootstrap
from app.database_bootstrap import (
    BOOTSTRAP_NAME,
    SCHEMA_VERSION,
    bootstrap_database,
    database_bootstrap_readiness,
)


class FakeAcquire:
    def __init__(self, connection):
        self.connection = connection

    async def __aenter__(self):
        return self.connection

    async def __aexit__(self, *_):
        return None


class FakePool:
    def __init__(self, connection):
        self.connection = connection
        self.closed = False

    def acquire(self):
        return FakeAcquire(self.connection)

    async def close(self) -> None:
        self.closed = True


class FakeBootstrapConnection:
    def __init__(self) -> None:
        self.executed: list[tuple[str, tuple]] = []
        self.status_row = {
            "schema_version": SCHEMA_VERSION,
            "status": "ready",
            "failure_reason": None,
        }
        self.table_exists = True

    async def execute(self, query: str, *args):
        self.executed.append((query, args))
        if "database_bootstrap_status" in query and len(args) >= 3:
            self.status_row = {
                "schema_version": args[1],
                "status": args[2],
                "failure_reason": args[4],
            }
        return "OK"

    async def fetchval(self, *_):
        return self.table_exists

    async def fetchrow(self, *_):
        return self.status_row


def test_bootstrap_records_ready_after_running_store_fragments(monkeypatch: pytest.MonkeyPatch):
    connection = FakeBootstrapConnection()
    pool = FakePool(connection)

    async def create_pool(*_, **__):
        return pool

    monkeypatch.setattr(database_bootstrap.asyncpg, "create_pool", create_pool)
    monkeypatch.setattr(
        database_bootstrap,
        "store_schema_fragments",
        lambda: [
            ("first", "CREATE TABLE first(id int);"),
            ("second", "CREATE INDEX idx ON first(id);"),
        ],
    )

    readiness = asyncio.run(bootstrap_database("postgresql://test"))

    assert readiness.ready is True
    assert pool.closed is True
    executed_sql = "\n".join(query for query, _ in connection.executed)
    assert "pg_advisory_lock" in executed_sql
    assert "CREATE TABLE first" in executed_sql
    assert "CREATE INDEX idx" in executed_sql
    assert connection.status_row["status"] == "ready"


def test_readiness_reports_not_run_without_creating_schema(monkeypatch: pytest.MonkeyPatch):
    connection = FakeBootstrapConnection()
    connection.table_exists = False
    pool = FakePool(connection)

    async def create_pool(*_, **__):
        return pool

    monkeypatch.setattr(database_bootstrap.asyncpg, "create_pool", create_pool)

    readiness = asyncio.run(database_bootstrap_readiness("postgresql://test"))

    assert readiness.status == "not_run"
    assert all("CREATE TABLE" not in query for query, _ in connection.executed)


def test_bootstrap_records_failure_without_business_status_update(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = FakeBootstrapConnection()
    pool = FakePool(connection)

    async def create_pool(*_, **__):
        return pool

    monkeypatch.setattr(database_bootstrap.asyncpg, "create_pool", create_pool)
    monkeypatch.setattr(
        database_bootstrap,
        "store_schema_fragments",
        lambda: [("broken", "SELECT missing_schema_failure();")],
    )

    async def fail_on_schema(query: str, *args):
        connection.executed.append((query, args))
        if "missing_schema_failure" in query:
            raise database_bootstrap.asyncpg.PostgresError("schema fragment failed")
        if "database_bootstrap_status" in query and len(args) >= 3:
            connection.status_row = {
                "schema_version": args[1],
                "status": args[2],
                "failure_reason": args[4],
            }
        return "OK"

    connection.execute = fail_on_schema  # type: ignore[method-assign]

    with pytest.raises(database_bootstrap.DatabaseBootstrapError):
        asyncio.run(bootstrap_database("postgresql://test"))

    assert connection.status_row["status"] == "failed"
    assert "schema fragment failed" in connection.status_row["failure_reason"]
    assert all("UPDATE research_runs" not in query for query, _ in connection.executed)


def test_readiness_reports_incompatible_schema_version(monkeypatch: pytest.MonkeyPatch):
    connection = FakeBootstrapConnection()
    connection.status_row = {
        "schema_version": "platform-schema:older",
        "status": "ready",
        "failure_reason": None,
    }
    pool = FakePool(connection)

    async def create_pool(*_, **__):
        return pool

    monkeypatch.setattr(database_bootstrap.asyncpg, "create_pool", create_pool)

    readiness = asyncio.run(database_bootstrap_readiness("postgresql://test"))

    assert readiness.status == "incompatible"
    assert readiness.schema_version == "platform-schema:older"


def test_bootstrap_status_contract_is_stable() -> None:
    assert BOOTSTRAP_NAME == "platform_application_schema"
    assert SCHEMA_VERSION == "platform-schema:v1"
    assert "database_bootstrap_status" in database_bootstrap.BOOTSTRAP_STATUS_SCHEMA
    assert "bootstrap_name TEXT PRIMARY KEY" in database_bootstrap.BOOTSTRAP_STATUS_SCHEMA


@pytest.mark.parametrize(
    "module_name",
    [
        "app.web_research.store",
        "app.agent_runtime.store",
        "app.agentic_research.store",
        "app.evidence_summaries.store",
        "app.web_trust.store",
        "app.identity.store",
        "app.identity.audit",
        "app.local_models.store",
    ],
)
def test_runtime_store_connection_paths_do_not_run_schema_setup(module_name: str) -> None:
    module = __import__(module_name, fromlist=["dummy"])
    source = inspect.getsource(module)

    assert "execute_schema_setup" not in source


def test_compose_runs_database_bootstrap_before_api_and_worker() -> None:
    compose = (Path(__file__).resolve().parents[3] / "compose.yaml").read_text(
        encoding="utf-8"
    )

    assert "database-bootstrap:" in compose
    assert 'command: ["python", "-m", "app.database_bootstrap"]' in compose
    assert "service_completed_successfully" in compose
