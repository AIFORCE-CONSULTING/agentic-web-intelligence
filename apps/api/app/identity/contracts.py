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


class EnterpriseIdentityStatus(BaseModel):
    """Safe, credential-free visibility into the enterprise identity boundary."""

    mode: Literal["disabled", "invalid", "ready"]
    provider_name: str | None = None
    issuer_url: str | None = None
    detail: str


class SecurityAuditEvent(BaseModel):
    """A sanitized, append-only record of a platform security decision."""

    id: UUID
    actor_user_id: UUID | None = None
    workspace_id: UUID | None = None
    event_type: str
    outcome: Literal["succeeded", "denied"]
    occurred_at: datetime
    details: dict[str, object] = Field(default_factory=dict)


class SecurityAuditEventList(BaseModel):
    """Bounded security history for an administrator's workspace."""

    events: list[SecurityAuditEvent]
