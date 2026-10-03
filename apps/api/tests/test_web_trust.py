import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest

from app.agent_runtime.research_workflow import ResearchWorkflowUnavailable
from app.evidence_summaries.contracts import (
    EvidenceSummaryExecution,
    EvidenceSummaryExecutionSource,
    EvidenceSummaryWorkSet,
)
from app.evidence_summaries.service import (
    EvidenceSummaryAutomation,
    EvidenceSummaryService,
    EvidenceSummaryUnavailable,
)
from app.identity.contracts import AuthenticatedServiceIdentity, AuthenticatedUser
from app.main import create_app
from app.web_research.contracts import Evidence, ResearchRun, SourceCandidate, ToolPolicyError
from app.web_trust.contracts import EvidenceTrustEvaluation, TrustRuleOutcome
from app.web_trust.preflight import CandidatePreflightService
from app.web_trust.service import EvidenceTrustService


def evidence(url: str = "https://example.com/article", content_type: str = "text/html") -> Evidence:
    return Evidence(
        url=url,
        requested_url=url,
        redirect_result="no_redirect",
        retrieved_at=datetime.now(UTC),
        content_type=content_type,
        text="Stored public evidence.",
        content_hash="sha256:content",
        extraction_method="readability",
    )


def authenticated_app(app):
    """Provide an operator identity for trust-policy route tests."""

    user = AuthenticatedUser(
        id=uuid4(),
        email="operator@example.com",
        workspace_id=uuid4(),
        workspace_name="Test workspace",
        role="operator",
        authenticated_at=datetime.now(UTC),
    )

    class FakeIdentityService:
        async def current_user(self, _: object) -> AuthenticatedUser:
            return user

    app.state.identity_service = FakeIdentityService()
    return app, user


class FakeTrustStore:
    def __init__(self) -> None:
        self.current: EvidenceTrustEvaluation | None = None
        self.accept_calls = 0
        self.reject_calls = 0

    async def latest_evaluation(self, *_: object) -> EvidenceTrustEvaluation | None:
        return self.current

    async def ensure_policy(self, *_: object) -> None:
        return None

    async def record_evaluation(
        self, workspace_id, run_id, url, content_hash, policy_version, disposition, rules, version
    ):
        self.current = EvidenceTrustEvaluation(
            id=uuid4(),
            run_id=run_id,
            source_url=url,
            content_hash=content_hash,
            policy_version=policy_version,
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
        self.accept_calls += 1
        assert self.current is not None
        self.current = self.current.model_copy(
            update={
                "disposition": "eligible",
                "override_id": uuid4(),
                "override_outcome": "accepted",
                "override_actor_user_id": uuid4(),
                "override_reason": "Reviewed",
                "override_created_at": datetime.now(UTC),
            }
        )
        return self.current

    async def reject_evaluation(
        self,
        _workspace_id,
        _run_id,
        _source_url,
        _content_hash,
        actor_user_id,
        reason,
    ) -> EvidenceTrustEvaluation | None:
        self.reject_calls += 1
        assert self.current is not None
        self.current = self.current.model_copy(
            update={
                "disposition": "review_required",
                "override_id": uuid4(),
                "override_outcome": "rejected",
                "override_actor_user_id": actor_user_id,
                "override_reason": reason,
                "override_created_at": datetime.now(UTC),
            }
        )
        return self.current


def test_default_policy_allows_supported_web_evidence() -> None:
    store = FakeTrustStore()
    result = asyncio.run(EvidenceTrustService(store).evaluate(uuid4(), uuid4(), evidence()))

    assert result.disposition == "eligible"
    assert result.base_disposition == "eligible"
    assert {item.rule for item in result.rule_outcomes} == {
        "https_required",
        "content_type",
        "extraction_integrity",
        "extracted_size",
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

    repeated = asyncio.run(
        service.accept(
            workspace_id,
            run_id,
            result.source_url,
            result.content_hash,
            uuid4(),
            "Repeated request",
            None,
        )
    )

    assert repeated == accepted
    assert store.accept_calls == 1


def test_unsupported_content_requires_human_review_and_can_be_rejected_without_reason() -> None:
    store = FakeTrustStore()
    service = EvidenceTrustService(store)
    workspace_id, run_id = uuid4(), uuid4()
    result = asyncio.run(
        service.evaluate(workspace_id, run_id, evidence(content_type="application/pdf"))
    )

    rejected = asyncio.run(
        service.reject(
            workspace_id,
            run_id,
            result.source_url,
            result.content_hash,
            uuid4(),
            None,
        )
    )

    assert rejected is not None
    assert rejected.disposition == "review_required"
    assert rejected.base_disposition == "review_required"
    assert rejected.override_outcome == "rejected"
    assert rejected.override_reason is None

    repeated = asyncio.run(
        service.reject(
            workspace_id,
            run_id,
            result.source_url,
            result.content_hash,
            uuid4(),
            "Repeated rejection",
        )
    )

    assert repeated == rejected
    assert store.reject_calls == 1


def test_review_rejection_preserves_optional_reason() -> None:
    store = FakeTrustStore()
    service = EvidenceTrustService(store)
    workspace_id, run_id = uuid4(), uuid4()
    result = asyncio.run(
        service.evaluate(workspace_id, run_id, evidence(content_type="application/pdf"))
    )

    rejected = asyncio.run(
        service.reject(
            workspace_id,
            run_id,
            result.source_url,
            result.content_hash,
            uuid4(),
            "Navigation shell, not useful source evidence.",
        )
    )

    assert rejected is not None
    assert rejected.override_outcome == "rejected"
    assert rejected.override_reason == "Navigation shell, not useful source evidence."


def test_review_acceptance_expiry_must_be_in_the_future() -> None:
    store = FakeTrustStore()
    service = EvidenceTrustService(store)
    workspace_id, run_id = uuid4(), uuid4()
    result = asyncio.run(
        service.evaluate(workspace_id, run_id, evidence(content_type="application/pdf"))
    )

    with pytest.raises(ValueError, match="Acceptance expiry must be in the future"):
        asyncio.run(
            service.accept(
                workspace_id,
                run_id,
                result.source_url,
                result.content_hash,
                uuid4(),
                "The source is appropriate for this research.",
                datetime.now(UTC) - timedelta(minutes=1),
            )
        )


def test_review_acceptance_expiry_must_include_a_timezone() -> None:
    store = FakeTrustStore()
    service = EvidenceTrustService(store)
    workspace_id, run_id = uuid4(), uuid4()
    result = asyncio.run(
        service.evaluate(workspace_id, run_id, evidence(content_type="application/pdf"))
    )

    with pytest.raises(ValueError, match="Acceptance expiry must include a timezone"):
        asyncio.run(
            service.accept(
                workspace_id,
                run_id,
                result.source_url,
                result.content_hash,
                uuid4(),
                "The source is appropriate for this research.",
                datetime.now(),
            )
        )


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


def test_blocked_evidence_cannot_be_rejected_as_human_review() -> None:
    store = FakeTrustStore()
    service = EvidenceTrustService(store)
    workspace_id, run_id = uuid4(), uuid4()
    result = asyncio.run(service.evaluate(workspace_id, run_id, evidence(url="http://example.com")))

    assert result.disposition == "blocked"
    with pytest.raises(ValueError, match="Only evidence requiring review can be rejected"):
        asyncio.run(
            service.reject(
                workspace_id,
                run_id,
                result.source_url,
                result.content_hash,
                uuid4(),
                None,
            )
        )


def test_human_review_decision_cannot_be_changed_between_accept_and_reject() -> None:
    workspace_id, run_id = uuid4(), uuid4()
    accepted_store = FakeTrustStore()
    accepted_service = EvidenceTrustService(accepted_store)
    accepted_result = asyncio.run(
        accepted_service.evaluate(
            workspace_id, run_id, evidence(content_type="application/pdf")
        )
    )
    asyncio.run(
        accepted_service.accept(
            workspace_id,
            run_id,
            accepted_result.source_url,
            accepted_result.content_hash,
            uuid4(),
            "Appropriate source.",
            None,
        )
    )

    with pytest.raises(ValueError, match="already has a human decision"):
        asyncio.run(
            accepted_service.reject(
                workspace_id,
                run_id,
                accepted_result.source_url,
                accepted_result.content_hash,
                uuid4(),
                None,
            )
        )

    rejected_store = FakeTrustStore()
    rejected_service = EvidenceTrustService(rejected_store)
    rejected_result = asyncio.run(
        rejected_service.evaluate(
            workspace_id, run_id, evidence(content_type="application/pdf")
        )
    )
    asyncio.run(
        rejected_service.reject(
            workspace_id,
            run_id,
            rejected_result.source_url,
            rejected_result.content_hash,
            uuid4(),
            None,
        )
    )

    with pytest.raises(ValueError, match="already has a human decision"):
        asyncio.run(
            rejected_service.accept(
                workspace_id,
                run_id,
                rejected_result.source_url,
                rejected_result.content_hash,
                uuid4(),
                "Appropriate source.",
                None,
            )
        )


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
    assert research_store.results[0][-1]["trust_disposition"] == "eligible"
    assert research_store.results[0][-1]["final_url"] == available.url
    assert research_store.results[0][-1]["redirect_result"] == "no_redirect"
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


def test_candidate_preflight_requires_matching_runtime_authorization_before_extract() -> None:
    workspace_id, run_id = uuid4(), uuid4()
    source = SourceCandidate(rank=1, title="Authorized", url="https://example.com/source")
    now = datetime.now(UTC)

    class Store:
        def __init__(self) -> None:
            self.saved: list[Evidence] = []
            self.results: list[tuple[object, ...]] = []

        async def get_run(self, *_: object):
            return ResearchRun(
                id=run_id,
                question="agent identity",
                status="acquiring",
                created_at=now,
                updated_at=now,
                sources=[source],
            )

        async def mark_candidate_checking(self, *_: object) -> None:
            return None

        async def save_evidence(self, _run_id: object, value: Evidence) -> None:
            self.saved.append(value)

        async def record_candidate_preflight(self, *args: object, **kwargs: object) -> None:
            self.results.append((*args, kwargs))

        async def complete_candidate_preflight(self, *_: object) -> None:
            return None

    class Authority:
        def __init__(self) -> None:
            self.runtime_id, self.step_id, self.decision_id = uuid4(), uuid4(), uuid4()
            self.request = None

        async def ensure_research_assignment(self, *_: object):
            return SimpleNamespace(
                id=self.runtime_id,
                steps=[
                    SimpleNamespace(id=self.step_id, role="researcher", status="active")
                ],
            )

        async def discovered_source_topic(self, *_: object) -> str:
            return "identity"

        async def authorize_request(self, request):
            self.request = request
            return SimpleNamespace(id=self.decision_id, decision="allow")

    class Mcp:
        def __init__(self) -> None:
            self.called = False

        async def invoke_authorized(self, correlation, arguments, authority):
            self.called = True
            assert correlation.authorization_decision_id == authority.decision_id
            assert correlation.request_id == authority.request.request_id
            assert arguments == {"url": source.url}
            return evidence(url=source.url)

    store, authority, mcp = Store(), Authority(), Mcp()
    asyncio.run(
        CandidatePreflightService(
            store, EvidenceTrustService(FakeTrustStore())
        ).preflight_run_authorized(
            workspace_id, run_id, authority, mcp, [source.url]
        )
    )

    assert mcp.called is True
    assert authority.request.action == "web.extract"
    assert authority.request.topic_id == "identity"
    assert [item.url for item in store.saved] == [source.url]


def test_summary_automation_batches_eligible_candidates_within_execution_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id, run_id = uuid4(), uuid4()
    urls = [f"https://example.com/source-{index}" for index in range(6)]
    work_set = EvidenceSummaryWorkSet(
        id=uuid4(),
        workspace_id=workspace_id,
        run_id=run_id,
        status="waiting",
    )

    class FakeExecutionStore:
        async def get_work_set(self, *_: object) -> None:
            return None

        async def create_work_set(self, *_: object) -> EvidenceSummaryWorkSet:
            return work_set

        async def refresh_work_set(self, *_: object) -> EvidenceSummaryWorkSet:
            return work_set

    automation = EvidenceSummaryAutomation(
        object(), FakeExecutionStore(), object(), object()
    )
    batches: list[list[str]] = []

    async def start_for_urls(
        _: object, __: object, batch: list[str], ___: object, ____: object
    ) -> object:
        batches.append(batch)
        return SimpleNamespace(id=len(batches))

    monkeypatch.setattr(automation, "start_for_urls", start_for_urls)

    result = asyncio.run(
        automation.start_for_relevant_urls(
            workspace_id, run_id, urls, SimpleNamespace()
        )
    )

    assert batches == [urls[:5], urls[5:]]
    assert result == work_set


def test_summary_automation_reuses_a_completed_work_set() -> None:
    workspace_id, run_id, work_set_id = uuid4(), uuid4(), uuid4()
    existing = EvidenceSummaryWorkSet(
        id=work_set_id,
        workspace_id=workspace_id,
        run_id=run_id,
        status="completed",
        execution_ids=[uuid4()],
    )

    class FakeExecutionStore:
        async def get_work_set(self, *_: object) -> EvidenceSummaryWorkSet:
            return existing

        async def create_work_set(self, *_: object) -> None:
            raise AssertionError("A completed work set must be resumed, not replaced.")

    automation = EvidenceSummaryAutomation(
        object(), FakeExecutionStore(), object(), object()
    )

    result = asyncio.run(
        automation.start_for_relevant_urls(
            workspace_id,
            run_id,
            ["https://example.com/source"],
            SimpleNamespace(),
        )
    )

    assert result == existing


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
            self.failure_reasons.append(_[-2])

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


def test_effective_web_trust_policy_is_read_only_for_operators() -> None:
    app, _ = authenticated_app(create_app())

    async def request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.get("/v1/web-trust-policy")

    response = asyncio.run(request())

    assert response.status_code == 200
    assert response.json() == {
        "version": "local-default-v2",
        "rules": {
            "required_scheme": "https",
            "allowed_content_types": ["text/html", "text/plain"],
            "maximum_extracted_characters": 200_000,
            "unknown_content_type_disposition": "review_required",
            "redirect_metadata": (
                "Record the requested URL, final URL, and bounded retrieval result; "
                "redirects do not independently change trust disposition."
            ),
        },
    }


def test_trust_review_endpoint_requires_a_human_and_returns_the_recorded_acceptance() -> None:
    app = create_app()
    user = AuthenticatedUser(
        id=uuid4(), email="operator@example.com", workspace_id=uuid4(),
        workspace_name="Test", role="operator", authenticated_at=datetime.now(UTC),
    )
    run_id = uuid4()
    review = EvidenceTrustEvaluation(
        id=uuid4(), run_id=run_id, source_url="https://example.com/article",
        content_hash="sha256:content", policy_version="local-default-v2",
        disposition="review_required", base_disposition="review_required",
        rule_outcomes=[
            TrustRuleOutcome(rule="content_type", outcome="review_required", detail="Review.")
        ],
        component_version="web-trust-v2", created_at=datetime.now(UTC),
    )

    class FakeIdentityService:
        async def current_user(self, _: object) -> AuthenticatedUser:
            return user

    class FakeTrustService:
        resume_records: list[tuple[object, ...]] = []

        async def accept(self, *_: object) -> EvidenceTrustEvaluation:
            return review.model_copy(
                update={
                    "disposition": "eligible",
                    "override_outcome": "accepted",
                    "override_reason": "Reviewed",
                }
            )

        async def record_workflow_resume(self, *args: object) -> None:
            self.resume_records.append(args)

    app.state.identity_service = FakeIdentityService()
    app.state.web_trust_service = FakeTrustService()

    class FakeResearchStore:
        async def get_run(self, *_: object) -> object:
            return SimpleNamespace(status_version=4)

    resumed: list[tuple[object, ...]] = []

    class FakeWorkflowEntry:
        async def resume_after_review(self, *args: object) -> object:
            resumed.append(args)
            return SimpleNamespace(status="evaluating_relevance")

    app.state.research_store = FakeResearchStore()
    app.state.research_workflow_entry = FakeWorkflowEntry()

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
    assert response.json()["override_outcome"] == "accepted"
    assert response.json()["override_reason"] == "Reviewed"
    assert len(app.state.web_trust_service.resume_records) == 1
    assert resumed == [
        (user.workspace_id, run_id, review.source_url, review.content_hash, "accepted")
    ]


def test_trust_review_reject_endpoint_records_decision_and_resumes_without_reason() -> None:
    app = create_app()
    user = AuthenticatedUser(
        id=uuid4(), email="operator@example.com", workspace_id=uuid4(),
        workspace_name="Test", role="operator", authenticated_at=datetime.now(UTC),
    )
    run_id = uuid4()
    review = EvidenceTrustEvaluation(
        id=uuid4(), run_id=run_id, source_url="https://example.com/article",
        content_hash="sha256:content", policy_version="local-default-v2",
        disposition="review_required", base_disposition="review_required",
        rule_outcomes=[
            TrustRuleOutcome(rule="content_type", outcome="review_required", detail="Review.")
        ],
        component_version="web-trust-v2", created_at=datetime.now(UTC),
    )

    class FakeIdentityService:
        async def current_user(self, _: object) -> AuthenticatedUser:
            return user

    class FakeTrustService:
        resume_records: list[tuple[object, ...]] = []

        async def reject(self, *_: object) -> EvidenceTrustEvaluation:
            return review.model_copy(
                update={
                    "override_outcome": "rejected",
                    "override_reason": None,
                }
            )

        async def record_workflow_resume(self, *args: object) -> None:
            self.resume_records.append(args)

    app.state.identity_service = FakeIdentityService()
    app.state.web_trust_service = FakeTrustService()

    class FakeResearchStore:
        async def get_run(self, *_: object) -> object:
            return SimpleNamespace(status_version=4)

    resumed: list[tuple[object, ...]] = []

    class FakeWorkflowEntry:
        async def resume_after_review(self, *args: object) -> object:
            resumed.append(args)
            return SimpleNamespace(status="evaluating_relevance")

    app.state.research_store = FakeResearchStore()
    app.state.research_workflow_entry = FakeWorkflowEntry()

    async def request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.post(
                f"/v1/research/runs/{run_id}/evidence-trust/reject",
                json={
                    "source_url": review.source_url,
                    "content_hash": review.content_hash,
                },
            )

    response = asyncio.run(request())

    assert response.status_code == 200
    assert response.json()["disposition"] == "review_required"
    assert response.json()["override_outcome"] == "rejected"
    assert len(app.state.web_trust_service.resume_records) == 1
    assert resumed == [
        (user.workspace_id, run_id, review.source_url, review.content_hash, "rejected")
    ]


def test_trust_review_endpoints_reject_service_identity_callers() -> None:
    app = create_app()
    service_identity = AuthenticatedServiceIdentity(
        id=uuid4(),
        name="research-bot",
        workspace_id=uuid4(),
        workspace_name="Test",
        permissions=frozenset({"research.write"}),
        authenticated_at=datetime.now(UTC),
    )
    run_id = uuid4()

    class FakeIdentityService:
        async def current_user(self, _: object) -> None:
            return None

        async def current_service_identity(self, _: object) -> AuthenticatedServiceIdentity:
            return service_identity

    class FakeTrustService:
        called = False

        async def accept(self, *_: object) -> None:
            self.called = True

        async def reject(self, *_: object) -> None:
            self.called = True

    app.state.identity_service = FakeIdentityService()
    app.state.web_trust_service = FakeTrustService()

    async def request(path: str, body: dict[str, object]) -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.post(
                path,
                headers={"Authorization": "Bearer service-token"},
                json=body,
            )

    accept_response = asyncio.run(
        request(
            f"/v1/research/runs/{run_id}/evidence-trust/accept",
            {
                "source_url": "https://example.com/article",
                "content_hash": "sha256:content",
                "reason": "Reviewed.",
            },
        )
    )
    reject_response = asyncio.run(
        request(
            f"/v1/research/runs/{run_id}/evidence-trust/reject",
            {
                "source_url": "https://example.com/article",
                "content_hash": "sha256:content",
            },
        )
    )

    assert accept_response.status_code == 403
    assert reject_response.status_code == 403
    assert "human operator" in accept_response.json()["detail"]
    assert "human operator" in reject_response.json()["detail"]
    assert app.state.web_trust_service.called is False


def test_reject_endpoint_can_retry_after_workflow_resume_failure() -> None:
    app = create_app()
    user = AuthenticatedUser(
        id=uuid4(), email="operator@example.com", workspace_id=uuid4(),
        workspace_name="Test", role="operator", authenticated_at=datetime.now(UTC),
    )
    run_id = uuid4()
    decision_id = uuid4()
    review = EvidenceTrustEvaluation(
        id=uuid4(), run_id=run_id, source_url="https://example.com/article",
        content_hash="sha256:content", policy_version="local-default-v2",
        disposition="review_required", base_disposition="review_required",
        rule_outcomes=[
            TrustRuleOutcome(rule="content_type", outcome="review_required", detail="Review.")
        ],
        component_version="web-trust-v2", created_at=datetime.now(UTC),
        override_id=decision_id, override_outcome="rejected",
    )

    class FakeIdentityService:
        async def current_user(self, _: object) -> AuthenticatedUser:
            return user

    class FakeTrustService:
        reject_calls = 0
        resume_records: list[tuple[object, ...]] = []

        async def reject(self, *_: object) -> EvidenceTrustEvaluation:
            self.reject_calls += 1
            return review

        async def record_workflow_resume(self, *args: object) -> None:
            self.resume_records.append(args)

    class FakeResearchStore:
        async def get_run(self, *_: object) -> object:
            return SimpleNamespace(status_version=4)

    class FakeWorkflowEntry:
        attempts = 0

        async def resume_after_review(self, *args: object) -> object:
            self.attempts += 1
            if self.attempts == 1:
                raise ResearchWorkflowUnavailable("Checkpoint store is unavailable.")
            return SimpleNamespace(status="evaluating_relevance")

    app.state.identity_service = FakeIdentityService()
    app.state.web_trust_service = FakeTrustService()
    app.state.research_store = FakeResearchStore()
    app.state.research_workflow_entry = FakeWorkflowEntry()

    async def request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.post(
                f"/v1/research/runs/{run_id}/evidence-trust/reject",
                json={
                    "source_url": review.source_url,
                    "content_hash": review.content_hash,
                },
            )

    first_response = asyncio.run(request())
    second_response = asyncio.run(request())

    assert first_response.status_code == 503
    assert second_response.status_code == 200
    assert second_response.json()["override_id"] == str(decision_id)
    assert second_response.json()["override_outcome"] == "rejected"
    assert app.state.web_trust_service.reject_calls == 2
    assert len(app.state.web_trust_service.resume_records) == 2
    assert app.state.research_workflow_entry.attempts == 2
