"""Strict model-output contracts for agentic research planning."""

import json
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, RootModel, ValidationError, model_validator

MAX_RESEARCH_TOPICS = 3


class ResearchTopic(BaseModel):
    """One focused area of the operator's research question."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    topic_id: str = Field(
        min_length=3,
        max_length=64,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )
    topic: str = Field(min_length=10, max_length=512)
    search_query: str = Field(min_length=3, max_length=512)


TopicList = Annotated[list[ResearchTopic], Field(min_length=1, max_length=MAX_RESEARCH_TOPICS)]


class TopicPlan(RootModel[TopicList]):
    """A bounded JSON array of focused topics proposed for one research question."""

    @model_validator(mode="after")
    def require_unique_topic_ids(self) -> Self:
        topic_ids = [item.topic_id for item in self.root]
        if len(topic_ids) != len(set(topic_ids)):
            raise ValueError("Every topic_id must be unique within the research plan.")
        return self


class TopicPlanValidationError(ValueError):
    """Raised when model output cannot become a trusted topic plan."""


def parse_topic_plan(content: str) -> TopicPlan:
    """Validate raw model text as the exact JSON-array topic contract."""

    try:
        decoded = json.loads(content)
        return TopicPlan.model_validate(decoded)
    except (json.JSONDecodeError, ValidationError) as error:
        raise TopicPlanValidationError(
            "The local model returned an invalid topic-planning response."
        ) from error

