import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest

from app.evidence_summaries.contracts import (
    EvidenceSummaryExecution,
    EvidenceSummaryExecutionSource,
)
from app.evidence_summaries.service import (
    EvidenceSummaryAutomation,
    EvidenceSummaryService,
    EvidenceSummaryUnavailable,
)
from app.identity.contracts import AuthenticatedUser
from app.main import create_app
from app.web_research.contracts import Evidence, SourceCandidate, ToolPolicyError
from app.web_trust.contracts import EvidenceTrustEvaluation, TrustRuleOutcome
from app.web_trust.preflight import CandidatePreflightService
from app.web_trust.service import EvidenceTrustService


def evidence(url: str = "https://example.com/article", content_type: str = "text/html") -> Evidence:
    return Evidence(
        url=url,
        retrieved_at=datetime.now(UTC),
        content_type=content_type,
        text="Stored public evidence.",
        content_hash="sha256:content",
        extraction_method="readability",
    )


class FakeTrustStore:
    def __init__(self) -> None:
        self.current: EvidenceTrustEvaluation | None = None

    async def latest_evaluation(self, *_: object) -> EvidenceTrustEvaluation | None:
        return self.current

    async def ensure_default_policy(self, *_: object) -> None:
        return None

    async def record_evaluation(
        self, workspace_id, run_id, url, content_hash, disposition, rules, version
    ):
        self.current = EvidenceTrustEvaluation(
            id=uuid4(),
            run_id=run_id,
            source_url=url,
            content_hash=content_hash,
            policy_version="local-default-v1",
            disposition=disposition,
            base_disposition=disposition,
            rule_outcomes=rules,
            component_version=version,
            created_at=datetime.now(UTC),
        )
        return self.current

    async def list_latest_evaluations(self, *_: object) -> list[EvidenceTrustEvaluation]:
        return [self.current] if self.current else []

    async def accept_evaluation(self, *_: object) -> EvidenceTrustEvaluation | None:
        assert self.current is not None
        self.current = self.current.model_copy(
            update={
                "disposition": "eligible",
                "override_id": uuid4(),
                "override_reason": "Reviewed",
            }
        )
        return self.current


def test_default_policy_allows_supported_web_evidence_with_a_notice() -> None:
    store = FakeTrustStore()
    result = asyncio.run(EvidenceTrustService(store).evaluate(uuid4(), uuid4(), evidence()))

    assert result.disposition == "eligible_with_notice"
    assert result.base_disposition == "eligible_with_notice"
    assert {item.rule for item in result.rule_outcomes} == {
        "https_required",
        "content_type",
        "extraction_integrity",
        "extracted_size",
        "redirect_history",
    }


def test_unsupported_content_requires_human_review_and_can_be_accepted() -> None:
    store = FakeTrustStore()
    service = EvidenceTrustService(store)
    workspace_id, run_id = uuid4(), uuid4()
    result = asyncio.run(
        service.evaluate(workspace_id, run_id, evidence(content_type="application/pdf"))
    )

    assert result.disposition == "review_required"
    accepted = asyncio.run(
        service.accept(
            workspace_id, run_id, result.source_url, result.content_hash,
            uuid4(), "The source is appropriate for this research.", None,
        )
    )
    assert accepted is not None
    assert accepted.disposition == "eligible"
    assert accepted.override_reason == "Reviewed"


def test_large_extracted_text_requires_human_review() -> None:
    store = FakeTrustStore()
    source = evidence().model_copy(update={"text": "x" * 200_001})

    result = asyncio.run(EvidenceTrustService(store).evaluate(uuid4(), uuid4(), source))

    assert result.disposition == "review_required"
    size_rule = next(rule for rule in result.rule_outcomes if rule.rule == "extracted_size")
    assert size_rule.outcome == "review_required"


def test_non_https_evidence_is_blocked_and_cannot_be_accepted() -> None:
    store = FakeTrustStore()
    service = EvidenceTrustService(store)
    workspace_id, run_id = uuid4(), uuid4()
    result = asyncio.run(service.evaluate(workspace_id, run_id, evidence(url="http://example.com")))

    assert result.disposition == "blocked"
    try:
        asyncio.run(
            service.accept(
                workspace_id,
                run_id,
                result.source_url,
                result.content_hash,
                uuid4(),
                "No.",
                None,
            )
        )
    except ValueError as error:
        assert str(error) == "Only evidence requiring review can be accepted."
    else:
        raise AssertionError("Blocked evidence must not be accepted.")


def test_candidate_preflight_persists_reusable_evidence_and_failed_candidate_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id, run_id = uuid4(), uuid4()
    available = SourceCandidate(rank=1, title="Available", url="https://example.com/available")
    blocked = SourceCandidate(rank=2, title="Blocked", url="https://example.com/blocked")

    class FakeResearchStore:
        def __init__(self) -> None:
            self.saved: list[Evidence] = []
            self.results: list[tuple[object, ...]] = []
            self.completed = False

        async def get_run(self, *_: object):
            return SimpleNamespace(sources=[available, blocked], evidence=[])

        async def mark_candidate_checking(self, *_: object) -> None:
            return None

        async def save_evidence(self, _: object, source: Evidence) -> None:
            self.saved.append(source)

        async def record_candidate_preflight(self, *args: object, **kwargs: object) -> None:
            self.results.append((*args, kwargs))

        async def complete_candidate_preflight(self, _: object) -> None:
            self.completed = True

    async def extract(url: str) -> Evidence:
        if url == blocked.url:
            raise ToolPolicyError("The response exceeds the maximum permitted size.")
        return evidence(url=url)

    monkeypatch.setattr("app.web_trust.preflight.run_extract_workflow", extract)
    research_store = FakeResearchStore()
    asyncio.run(
        CandidatePreflightService(
            research_store, EvidenceTrustService(FakeTrustStore())
        ).preflight_run(workspace_id, run_id)
    )

    assert [item.url for item in research_store.saved] == [available.url]
    assert research_store.results[0][2] == "ready_to_extract"
    assert research_store.results[0][-1]["trust_disposition"] == "eligible_with_notice"
    assert research_store.results[1][2] == "blocked"
    assert "maximum permitted size" in str(research_store.results[1][3])
    assert research_store.completed is True


def test_candidate_preflight_evaluates_captured_checking_evidence_without_refetching(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id, run_id = uuid4(), uuid4()
    source = SourceCandidate(
        rank=1,
        title="Captured",
        url="https://example.com/captured",
        preflight_status="checking",
    )
    captured = evidence(url=source.url)

    class FakeResearchStore:
        def __init__(self) -> None:
            self.saved: list[Evidence] = []
            self.results: list[tuple[object, ...]] = []

        async def get_run(self, *_: object):
            return SimpleNamespace(sources=[source], evidence=[captured])

        async def mark_candidate_checking(self, *_: object) -> None:
            raise AssertionError("Captured evidence must not be fetched again.")

        async def save_evidence(self, _: object, value: Evidence) -> None:
            self.saved.append(value)

        async def record_candidate_preflight(self, *args: object, **kwargs: object) -> None:
            self.results.append((*args, kwargs))

        async def complete_candidate_preflight(self, _: object) -> None:
            return None

    async def extract(_: str) -> Evidence:
        raise AssertionError("Captured evidence must not be extracted again.")

    monkeypatch.setattr("app.web_trust.preflight.run_extract_workflow", extract)
    store = FakeResearchStore()
    asyncio.run(
        CandidatePreflightService(store, EvidenceTrustService(FakeTrustStore())).preflight_run(
            workspace_id, run_id, [source.url]
        )
    )

    assert store.saved == []
    assert store.results[0][2] == "ready_to_extract"


def test_summary_automation_batches_eligible_candidates_within_execution_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id, run_id = uuid4(), uuid4()
    urls = [f"https://example.com/source-{index}" for index in range(6)]

    class FakeResearchStore:
        async def get_run(self, *_: object):
            return SimpleNamespace(
                sources=[
                    SourceCandidate(
                        rank=index + 1,
                        title=f"Source {index}",
                        url=url,
                        preflight_status="ready_to_extract",
                    )
                    for index, url in enumerate(urls)
                ]
            )

    automation = EvidenceSummaryAutomation(
        object(), object(), FakeResearchStore(), object()
    )
    batches: list[list[str]] = []

    async def start_for_urls(_: object, __: object, batch: list[str]) -> object:
        batches.append(batch)
        return SimpleNamespace(id=len(batches))

    monkeypatch.setattr(automation, "start_for_urls", start_for_urls)

    result = asyncio.run(automation.start_for_discovered_candidates(workspace_id, run_id, urls))

    assert batches == [urls[:5], urls[5:]]
    assert result.id == 2


def test_summary_preparation_excludes_evidence_requiring_review() -> None:
    workspace_id, run_id, execution_id = uuid4(), uuid4(), uuid4()
    source = evidence(content_type="application/pdf")
    execution = EvidenceSummaryExecution(
        id=execution_id,
        workspace_id=workspace_id,
        run_id=run_id,
        route="undetermined",
        status="extracting",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        sources=[EvidenceSummaryExecutionSource(url=source.url)],
    )

    class FakeExecutionStore:
        failure_reasons: list[str] = []

        async def record_source_failure(self, *_: object) -> None:
            self.failure_reasons.append(_[-1])

        async def get_execution(self, *_: object) -> EvidenceSummaryExecution:
            return execution

    class FakeResearchStore:
        async def get_run(self, *_: object):
            return SimpleNamespace(evidence=[source])

    class ReviewTrustService:
        async def evaluate(self, *_: object):
            return SimpleNamespace(disposition="review_required")

    store = FakeExecutionStore()
    service = EvidenceSummaryService(store, FakeResearchStore(), object(), ReviewTrustService())

    with pytest.raises(EvidenceSummaryUnavailable, match="No successfully extracted"):
        asyncio.run(service.prepare(execution))
    assert store.failure_reasons == ["Evidence requires human review before it can be summarized."]


def test_trust_review_endpoint_requires_a_human_and_returns_the_recorded_acceptance() -> None:
    app = create_app()
    user = AuthenticatedUser(
        id=uuid4(), email="operator@example.com", workspace_id=uuid4(),
        workspace_name="Test", role="operator", authenticated_at=datetime.now(UTC),
    )
    run_id = uuid4()
    review = EvidenceTrustEvaluation(
        id=uuid4(), run_id=run_id, source_url="https://example.com/article",
        content_hash="sha256:content", policy_version="local-default-v1",
        disposition="review_required", base_disposition="review_required",
        rule_outcomes=[
            TrustRuleOutcome(rule="content_type", outcome="review_required", detail="Review.")
        ],
        component_version="web-trust-v1", created_at=datetime.now(UTC),
    )

    class FakeIdentityService:
        async def current_user(self, _: object) -> AuthenticatedUser:
            return user

    class FakeTrustService:
        async def accept(self, *_: object) -> EvidenceTrustEvaluation:
            return review.model_copy(
                update={"disposition": "eligible", "override_reason": "Reviewed"}
            )

    app.state.identity_service = FakeIdentityService()
    app.state.web_trust_service = FakeTrustService()

    class FakeSummaryAutomation:
        async def start_for_urls(self, *_: object) -> None:
            return None

    app.state.evidence_summary_automation = FakeSummaryAutomation()

    async def request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.post(
                f"/v1/research/runs/{run_id}/evidence-trust/accept",
                json={
                    "source_url": review.source_url,
                    "content_hash": review.content_hash,
                    "reason": "Reviewed against the source context.",
                },
            )

    response = asyncio.run(request())

    assert response.status_code == 200
    assert response.json()["disposition"] == "eligible"
    assert response.json()["override_reason"] == "Reviewed"
