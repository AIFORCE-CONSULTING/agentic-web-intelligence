"""Production topic planning through the configured local Ollama model."""

from collections.abc import Callable
from uuid import UUID

from ollama import AsyncClient, RequestError, ResponseError

from app.agentic_research.contracts import (
    TopicPlan,
    TopicPlanValidationError,
    parse_topic_plan,
)
from app.agentic_research.planning import (
    TOPIC_PLANNING_PROMPT_VERSION,
    topic_planning_messages,
)
from app.agentic_research.store import AgenticResearchStore
from app.local_models.service import LocalModelProviderService

ClientFactory = Callable[[str], AsyncClient]


class TopicPlanningUnavailable(RuntimeError):
    """Raised when the configured local model cannot produce a valid plan."""


class TopicPlanningService:
    """Generate, validate, and store one immutable topic plan."""

    def __init__(
        self,
        store: AgenticResearchStore,
        provider_service: LocalModelProviderService,
        client_factory: ClientFactory | None = None,
    ) -> None:
        self._store = store
        self._provider_service = provider_service
        self._client_factory = client_factory or (lambda host: AsyncClient(host=host, timeout=120))

    async def plan(self, workspace_id: UUID, run_id: UUID, question: str) -> TopicPlan:
        configuration = await self._provider_service.configuration(workspace_id)
        if configuration is None:
            raise TopicPlanningUnavailable("A local Ollama provider is not configured.")
        try:
            response = await self._client_factory(configuration.endpoint_url).chat(
                model=configuration.model_name,
                messages=topic_planning_messages(question),
                format=TopicPlan.model_json_schema(),
                think=True,
                options={"temperature": 0.0},
            )
            plan = parse_topic_plan(response.message.content or "")
        except (RequestError, ResponseError, OSError, TopicPlanValidationError) as error:
            raise TopicPlanningUnavailable(
                "The local model could not produce a valid topic plan."
            ) from error
        await self._store.save_topic_plan(
            workspace_id,
            run_id,
            plan,
            TOPIC_PLANNING_PROMPT_VERSION,
        )
        return plan
