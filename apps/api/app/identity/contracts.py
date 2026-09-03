"""Typed contracts for human identity and browser sessions."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

WorkspaceRole = Literal["administrator", "operator", "viewer"]


class BootstrapAdminRequest(BaseModel):
    """One-time deployment-controlled initialization; closed after first use."""

    model_config = ConfigDict(extra="forbid")

    bootstrap_secret: str = Field(min_length=32, max_length=512)
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=14, max_length=256)


class SignInRequest(BaseModel):
    """Local credential sign-in; passwords are never returned or logged."""

    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=256)


class AuthenticatedUser(BaseModel):
    """The safe browser-visible identity and its current workspace authority."""

    id: UUID
    email: str
    workspace_id: UUID
    workspace_name: str
    role: WorkspaceRole
    authenticated_at: datetime
