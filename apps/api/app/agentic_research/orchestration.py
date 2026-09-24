"""Platform-owned routing for the bounded agentic research workflow."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

MAX_GAP_SEARCH_ROUNDS = 2

ResearchWorkflowStage = Literal[
    "requested",
    "topics_planned",
    "sources_discovered",
    "evidence_acquired",
    "relevance_decided",
    "summaries_stored",
    "coverage_complete",
    "coverage_incomplete",
    "awaiting_review",
    "report_stored",
    "completed",
    "failed",
    "cancelled",
]

ResearchWorkflowAction = Literal[
    "plan_topics",
    "search_topics",
    "acquire_evidence",
    "evaluate_relevance",
    "summarize_evidence",
    "assess_topic_coverage",
    "search_missing_topic",
    "generate_final_report",
    "complete_research",
    "wait_for_human_review",
    "none",
]


class ResearchOrchestrationSnapshot(BaseModel):
    """Official workflow facts supplied by the platform's persistence boundary."""

    model_config = ConfigDict(extra="forbid")

    workspace_id: UUID
    run_id: UUID
    stage: ResearchWorkflowStage
    source_limit: int = Field(ge=5, le=50)
    gap_search_rounds: int = Field(ge=0, le=MAX_GAP_SEARCH_ROUNDS)
    uncovered_topic_ids: list[str] = Field(default_factory=list, max_length=3)

    @model_validator(mode="after")
    def require_coverage_facts_only_during_coverage(self) -> "ResearchOrchestrationSnapshot":
        if self.stage == "coverage_complete" and self.uncovered_topic_ids:
            raise ValueError("Completed topic coverage cannot contain uncovered topics.")
        if self.stage == "coverage_incomplete" and not self.uncovered_topic_ids:
            raise ValueError("Incomplete topic coverage must identify an uncovered topic.")
        return self


class ResearchOrchestrationDirective(BaseModel):
    """One bounded instruction for a separate platform component to perform."""

    model_config = ConfigDict(extra="forbid")

    action: ResearchWorkflowAction
    reason: str
    topic_id: str | None = None
    gap_search_round: int | None = Field(default=None, ge=1, le=MAX_GAP_SEARCH_ROUNDS)


class ResearchOrchestrationService:
    """Choose the next approved workflow action without executing or storing it."""

    def next_action(
        self, snapshot: ResearchOrchestrationSnapshot
    ) -> ResearchOrchestrationDirective:
        """Return one deterministic next action from officially stored progress."""

        if snapshot.stage == "requested":
            return self._directive(
                "plan_topics", "The recorded operator question is ready for topic planning."
            )
        if snapshot.stage == "topics_planned":
            return self._directive(
                "search_topics", "The validated topic plan is ready for bounded searches."
            )
        if snapshot.stage == "sources_discovered":
            return self._directive(
                "acquire_evidence",
                "Discovered candidates are ready for governed evidence acquisition.",
            )
        if snapshot.stage == "evidence_acquired":
            return self._directive(
                "evaluate_relevance",
                "Eligible evidence is ready for topic-specific relevance decisions.",
            )
        if snapshot.stage == "relevance_decided":
            return self._directive(
                "summarize_evidence",
                "Eligible and relevant evidence is ready for the summary workflow.",
            )
        if snapshot.stage == "summaries_stored":
            return self._directive(
                "assess_topic_coverage",
                "Stored summaries and keywords are ready for deterministic coverage checks.",
            )
        if snapshot.stage == "coverage_complete":
            return self._directive(
                "generate_final_report",
                "Every planned topic has qualifying stored evidence.",
            )
        if snapshot.stage == "coverage_incomplete":
            if snapshot.gap_search_rounds >= MAX_GAP_SEARCH_ROUNDS:
                return self._directive(
                    "generate_final_report",
                    "The gap-search limit is exhausted; the report must disclose missing evidence.",
                )
            topic_id = snapshot.uncovered_topic_ids[0]
            return ResearchOrchestrationDirective(
                action="search_missing_topic",
                reason="A planned topic lacks qualifying evidence.",
                topic_id=topic_id,
                gap_search_round=snapshot.gap_search_rounds + 1,
            )
        if snapshot.stage == "awaiting_review":
            return self._directive(
                "wait_for_human_review",
                "Evidence awaiting review cannot enter automated model context.",
            )
        if snapshot.stage == "report_stored":
            return self._directive(
                "complete_research",
                "The validated final report is stored and the task can be completed.",
            )
        return self._directive(
            "none", f"The research task is already {snapshot.stage}."
        )

    @staticmethod
    def _directive(action: ResearchWorkflowAction, reason: str) -> ResearchOrchestrationDirective:
        return ResearchOrchestrationDirective(action=action, reason=reason)
