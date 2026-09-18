"""Typed records for platform-owned web-evidence eligibility decisions."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

TrustDisposition = Literal["eligible", "eligible_with_notice", "review_required", "blocked"]


class TrustRuleOutcome(BaseModel):
    """One deterministic rule result retained with an evaluation."""

    rule: str
    outcome: Literal["passed", "notice", "review_required", "blocked"]
    detail: str


class EvidenceTrustEvaluation(BaseModel):
    """The effective local eligibility for one captured evidence version."""

    id: UUID
    run_id: UUID
    source_url: str
    content_hash: str
    policy_version: str
    disposition: TrustDisposition
    base_disposition: TrustDisposition
    rule_outcomes: list[TrustRuleOutcome]
    component_version: str
    created_at: datetime
    override_id: UUID | None = None
    override_reason: str | None = None
    override_expires_at: datetime | None = None


class EvidenceTrustEvaluationList(BaseModel):
    """The latest evaluation for each captured evidence version in a run."""

    evaluations: list[EvidenceTrustEvaluation]


class CreateEvidenceTrustOverrideRequest(BaseModel):
    """A human acceptance for one exact captured evidence version."""

    model_config = ConfigDict(extra="forbid")

    source_url: str = Field(min_length=1, max_length=2_048)
    content_hash: str = Field(min_length=8, max_length=256)
    reason: str = Field(min_length=3, max_length=500)
    expires_at: datetime | None = None
