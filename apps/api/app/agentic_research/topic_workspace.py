"""Topic notebook coordination without a second workflow or trust authority."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.agent_runtime.research_workflow import UnifiedResearchWorkflowEntry
from app.agentic_research.contracts import (
    TopicAttentionItem,
    TopicQuestionSummary,
    TopicSourceLibrary,
    TopicWikiRevision,
    TopicWorkspace,
    TopicWorkspaceSummary,
)
from app.agentic_research.store import AgenticResearchStore
from app.web_research.contracts import ResearchRun
from app.web_research.store import ResearchStore, TopicReviewPendingError


class TopicWorkspaceConflict(ValueError):
    """A topic action cannot proceed until the operator resolves attention items."""

    def __init__(self, items: list[TopicAttentionItem]) -> None:
        super().__init__("Evidence in this topic needs an operator decision first.")
        self.items = items


@dataclass(frozen=True)
class TopicQuestionStart:
    """The stored research record returned after topic-scoped start or reuse."""

    run: ResearchRun
    created: bool


class TopicWorkspaceService:
    """Coordinates Topic identity and membership through existing owners."""

    def __init__(
        self,
        agentic_store: AgenticResearchStore,
        research_store: ResearchStore,
        workflow_entry: UnifiedResearchWorkflowEntry,
    ) -> None:
        self._agentic_store = agentic_store
        self._research_store = research_store
        self._workflow_entry = workflow_entry

    async def create_or_get(self, workspace_id: UUID, name: str) -> TopicWorkspaceSummary:
        return await self._agentic_store.create_or_get_topic(workspace_id, name)

    async def list(self, workspace_id: UUID) -> list[TopicWorkspaceSummary]:
        return await self._agentic_store.list_topics(workspace_id)

    async def get(self, workspace_id: UUID, topic_id: UUID) -> TopicWorkspace | None:
        return await self._agentic_store.get_topic_workspace(workspace_id, topic_id)

    async def questions(
        self, workspace_id: UUID, topic_id: UUID
    ) -> list[TopicQuestionSummary]:
        return await self._agentic_store.list_topic_questions(workspace_id, topic_id)

    async def sources(self, workspace_id: UUID, topic_id: UUID) -> TopicSourceLibrary:
        return await self._agentic_store.topic_source_library(workspace_id, topic_id)

    async def revisions(self, workspace_id: UUID, topic_id: UUID) -> list[TopicWikiRevision]:
        return await self._agentic_store.list_topic_wiki_revisions(workspace_id, topic_id)

    async def start_question(
        self,
        workspace_id: UUID,
        topic_id: UUID,
        question: str,
        source_limit: int,
    ) -> TopicQuestionStart:
        """Attach one question then invoke the existing governed graph."""

        await self._workflow_entry.ensure_start_ready()
        try:
            run, created = await self._research_store.get_or_create_topic_run(
                workspace_id, topic_id, question
            )
        except TopicReviewPendingError as error:
            raise TopicWorkspaceConflict(
                await self._agentic_store.topic_attention_items(workspace_id, topic_id)
            ) from error
        persisted = await self._workflow_entry.start_existing(
            workspace_id, run, question, source_limit, topic_id=topic_id
        )
        return TopicQuestionStart(run=persisted, created=created)
