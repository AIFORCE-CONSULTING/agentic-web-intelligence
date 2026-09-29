"""Tests for production topic planning and its LangGraph adapter."""

import asyncio
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.agent_runtime.research_workflow import topic_planning_node
from app.agentic_research.topic_planning import (
    TopicPlanningService,
    TopicPlanningUnavailable,
)


class FakeStore:
    def __init__(self) -> None:
        self.saved: tuple[object, ...] | None = None

    async def save_topic_plan(self, *values: object) -> list[object]:
        self.saved = values
        return []


class FakeProviderService:
    async def configuration(self, _: object) -> object:
        return SimpleNamespace(endpoint_url="http://localhost:11434", model_name="qwen3:1.7b")


class FakeClient:
    def __init__(self, content: str) -> None:
        self.content = content
        self.request: dict[str, object] | None = None

    async def chat(self, **request: object) -> object:
        self.request = request
        return SimpleNamespace(message=SimpleNamespace(content=self.content))


def valid_plan() -> str:
    return json.dumps(
        [
            {
                "topic_id": "agent-identity",
                "topic": "How autonomous websites disclose agent identity",
                "search_query": "agentic website autonomous agent identity disclosure",
            }
        ]
    )


def test_service_uses_schema_and_stores_the_validated_plan() -> None:
    workspace_id = uuid4()
    run_id = uuid4()
    store = FakeStore()
    client = FakeClient(valid_plan())
    service = TopicPlanningService(
        store, FakeProviderService(), client_factory=lambda _: client
    )

    plan = asyncio.run(service.plan(workspace_id, run_id, "How can agents identify websites?"))

    assert plan.root[0].topic_id == "agent-identity"
    assert store.saved is not None
    assert store.saved[:3] == (workspace_id, run_id, plan)
    assert client.request is not None
    assert client.request["format"] == plan.model_json_schema()
    assert client.request["think"] is True
    assert client.request["options"] == {"temperature": 0.0}


def test_invalid_model_output_fails_without_saving() -> None:
    store = FakeStore()
    service = TopicPlanningService(
        store,
        FakeProviderService(),
        client_factory=lambda _: FakeClient('{"topic_id":"not-an-array"}'),
    )

    with pytest.raises(TopicPlanningUnavailable):
        asyncio.run(service.plan(uuid4(), uuid4(), "Research agent identity"))

    assert store.saved is None


def test_langgraph_node_returns_the_stored_topic_plan_as_working_state() -> None:
    service = TopicPlanningService(
        FakeStore(),
        FakeProviderService(),
        client_factory=lambda _: FakeClient(valid_plan()),
    )
    state = {
        "workspace_id": uuid4(),
        "run_id": uuid4(),
        "question": "How can agents identify websites?",
        "source_limit": 10,
        "stage": "requested",
    }

    update = asyncio.run(topic_planning_node(service)(state))

    assert update["stage"] == "topics_planned"
    assert update["topics"][0].topic_id == "agent-identity"
