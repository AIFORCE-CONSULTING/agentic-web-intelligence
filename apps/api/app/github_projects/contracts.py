"""Safe, typed contracts for the narrow GitHub Projects integration."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class GitHubProjectStatus(BaseModel):
    """Credential-free readiness for the one configured GitHub Project."""

    mode: Literal["disabled", "invalid", "ready"]
    owner: str | None = None
    project_number: int | None = None
    project_url: str | None = None
    detail: str


class GitHubProjectInfo(BaseModel):
    """Safe Project metadata and the Priority options the operator may select."""

    title: str
    owner: str
    project_number: int
    project_url: str
    priority_options: list[str]


class CreateDraftItemRequest(BaseModel):
    """The only GitHub write initially exposed by the platform."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=256)
    body: str | None = Field(default=None, max_length=65536)
    priority: str | None = Field(default=None, min_length=1, max_length=80)


class UpdateDraftItemPriorityRequest(BaseModel):
    """A bounded update to the configured Project's Priority field."""

    model_config = ConfigDict(extra="forbid")

    priority: str = Field(min_length=1, max_length=80)


class GitHubDraftItem(BaseModel):
    """Safe record returned after GitHub creates or updates a draft item."""

    id: str
    title: str
    priority: str | None = None


class GitHubDraftItemList(BaseModel):
    """A bounded list of draft-only roadmap items from the configured Project."""

    items: list[GitHubDraftItem]
