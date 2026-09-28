import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from app.evidence_summaries.contracts import EvidenceSummaryExecution
from app.research_durable_work import ResearchDurableWorkService
from app.web_research.contracts import AuditEvent, ResearchRun, SourceCandidate


def test_durable_work_uses_stored_application_routes_and_canonical_status() -> None:
    workspace_id, run_id, execution_id = uuid4(), uuid4(), uuid4()
    now = datetime.now(UTC)
    run = ResearchRun(
        id=run_id,
        question="agent-ready websites",
        status="summarizing",
        created_at=now,
        updated_at=now,
        sources=[
            SourceCandidate(
                rank=1,
                title="Source",
                url="https://example.com",
                preflight_status="ready_to_extract",
                preflight_checked_at=now,
            )
        ],
        audit_events=[
            AuditEvent(
                event_type="research.candidate.preflight.routed",
                occurred_at=now,
                details={"route": "temporal", "source_count": 1},
            )
        ],
    )
    summary = EvidenceSummaryExecution(
        id=execution_id,
        workspace_id=workspace_id,
        run_id=run_id,
        route="direct",
        status="summarizing",
        created_at=now,
        updated_at=now,
        sources=[],
    )

    class ResearchStore:
        async def get_run(self, requested_workspace, requested_run):
            assert (requested_workspace, requested_run) == (workspace_id, run_id)
            return run

    class SummaryStore:
        async def get_latest_execution_for_run(self, *_):
            return summary

    item = asyncio.run(
        ResearchDurableWorkService(ResearchStore(), SummaryStore()).get(
            workspace_id, run_id
        )
    )

    assert item is not None
    assert item.research_status == "summarizing"
    actual_operations = [
        (operation.operation_type, operation.route, operation.status)
        for operation in item.operations
    ]
    assert actual_operations == [
        ("candidate_preflight", "temporal", "completed"),
        ("evidence_summary", "direct", "summarizing"),
    ]


def test_durable_work_list_excludes_runs_without_owned_operations() -> None:
    workspace_id, empty_run_id, active_run_id = uuid4(), uuid4(), uuid4()
    now = datetime.now(UTC)
    runs = {
        empty_run_id: ResearchRun(
            id=empty_run_id,
            question="not started",
            status="planning",
            created_at=now,
            updated_at=now,
        ),
        active_run_id: ResearchRun(
            id=active_run_id,
            question="active",
            status="acquiring",
            created_at=now,
            updated_at=now,
            sources=[
                SourceCandidate(
                    rank=1,
                    title="Source",
                    url="https://example.com",
                )
            ],
        ),
    }

    class ResearchStore:
        async def list_runs(self, requested_workspace, limit):
            assert requested_workspace == workspace_id
            assert limit == 25
            return [SimpleNamespace(id=empty_run_id), SimpleNamespace(id=active_run_id)]

        async def get_run(self, _workspace, run_id):
            return runs[run_id]

    class SummaryStore:
        async def get_latest_execution_for_run(self, *_):
            return None

    items = asyncio.run(
        ResearchDurableWorkService(ResearchStore(), SummaryStore()).list_for_workspace(
            workspace_id, 25
        )
    )

    assert [item.research_run_id for item in items] == [active_run_id]
