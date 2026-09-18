"""Deterministic, browser-independent evidence eligibility evaluation."""

from datetime import datetime
from urllib.parse import urlsplit
from uuid import UUID

from app.web_research.contracts import Evidence
from app.web_research.policy import MAX_EXTRACTED_TEXT_CHARS
from app.web_trust.contracts import EvidenceTrustEvaluation, TrustRuleOutcome
from app.web_trust.store import WebTrustStore

_POLICY_VERSION = "local-default-v1"
_COMPONENT_VERSION = "web-trust-v1"
_ALLOWED_CONTENT_TYPES = frozenset({"text/html", "text/plain"})


class EvidenceTrustService:
    """Apply only server-owned, deterministic policy to stored evidence."""

    def __init__(self, store: WebTrustStore) -> None:
        self._store = store

    async def evaluate(
        self, workspace_id: UUID, run_id: UUID, evidence: Evidence
    ) -> EvidenceTrustEvaluation:
        """Return the current effective eligibility for one exact evidence version."""

        existing = await self._store.latest_evaluation(
            workspace_id, run_id, evidence.url, evidence.content_hash
        )
        if existing is not None and existing.policy_version == _POLICY_VERSION:
            return existing
        rules = self._rules(evidence)
        await self._store.ensure_default_policy(workspace_id, self.default_policy())
        disposition = self._disposition(rules)
        return await self._store.record_evaluation(
            workspace_id, run_id, evidence.url, evidence.content_hash,
            disposition, rules, _COMPONENT_VERSION,
        )

    async def accept(
        self,
        workspace_id: UUID,
        run_id: UUID,
        source_url: str,
        content_hash: str,
        actor_user_id: UUID,
        reason: str,
        expires_at: datetime | None,
    ) -> EvidenceTrustEvaluation | None:
        """Persist a human acceptance for an already evaluated source version."""

        evaluation = await self._store.latest_evaluation(
            workspace_id, run_id, source_url, content_hash
        )
        if evaluation is None:
            return None
        if evaluation.base_disposition != "review_required":
            raise ValueError("Only evidence requiring review can be accepted.")
        return await self._store.accept_evaluation(
            workspace_id, run_id, source_url, content_hash, actor_user_id, reason, expires_at
        )

    async def list_for_run(self, workspace_id: UUID, run_id: UUID) -> list[EvidenceTrustEvaluation]:
        return await self._store.list_latest_evaluations(workspace_id, run_id)

    @staticmethod
    def default_policy() -> dict[str, object]:
        """Expose the fixed v1 rules recorded with each workspace policy version."""

        return {
            "required_scheme": "https",
            "allowed_content_types": sorted(_ALLOWED_CONTENT_TYPES),
            "maximum_extracted_characters": MAX_EXTRACTED_TEXT_CHARS,
            "unknown_content_type_disposition": "review_required",
        }

    @staticmethod
    def _rules(evidence: Evidence) -> list[TrustRuleOutcome]:
        parsed = urlsplit(evidence.url)
        content_type = evidence.content_type.split(";", 1)[0].strip().lower()
        rules = [
            TrustRuleOutcome(
                rule="https_required",
                outcome="passed" if parsed.scheme == "https" and parsed.hostname else "blocked",
                detail="The captured URL uses HTTPS."
                if parsed.scheme == "https" and parsed.hostname
                else "Evidence must have an HTTPS URL with a hostname.",
            ),
            TrustRuleOutcome(
                rule="content_type",
                outcome="passed" if content_type in _ALLOWED_CONTENT_TYPES else "review_required",
                detail=("The response type is supported for extracted web evidence."
                        if content_type in _ALLOWED_CONTENT_TYPES
                        else "The response type is outside the v1 extracted web-evidence policy."),
            ),
            TrustRuleOutcome(
                rule="extraction_integrity",
                outcome=("passed" if evidence.text and evidence.extraction_method
                         and evidence.content_hash.startswith("sha256:") else "blocked"),
                detail=("Extracted text, method, and content hash are present."
                        if evidence.text and evidence.extraction_method
                        and evidence.content_hash.startswith("sha256:")
                        else "Evidence is missing required extraction-integrity fields."),
            ),
            TrustRuleOutcome(
                rule="extracted_size",
                outcome=(
                    "passed"
                    if len(evidence.text) <= MAX_EXTRACTED_TEXT_CHARS
                    else "review_required"
                ),
                detail=("Extracted text is within the local policy limit."
                        if len(evidence.text) <= MAX_EXTRACTED_TEXT_CHARS
                        else "Extracted text requires human review before automated use."),
            ),
            TrustRuleOutcome(
                rule="redirect_history",
                outcome="notice",
                detail=(
                    "Redirect history is not retained by the current evidence contract."
                ),
            ),
        ]
        return rules

    @staticmethod
    def _disposition(rules: list[TrustRuleOutcome]) -> str:
        outcomes = {rule.outcome for rule in rules}
        if "blocked" in outcomes:
            return "blocked"
        if "review_required" in outcomes:
            return "review_required"
        if "notice" in outcomes:
            return "eligible_with_notice"
        return "eligible"
