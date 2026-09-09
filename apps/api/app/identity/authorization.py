"""Code-owned workspace permissions; request text never grants authority."""

from typing import Literal

from app.identity.contracts import (
    AuthenticatedServiceIdentity,
    AuthenticatedUser,
    WorkspaceRole,
)

WorkspacePermission = Literal[
    "research.read",
    "research.write",
    "runtime.read",
    "runtime.execute",
    "mcp.use",
    "mcp.audit.read",
    "security.audit.read",
    "service.identity.manage",
    "github.projects.manage",
]

ROLE_PERMISSIONS: dict[WorkspaceRole, frozenset[WorkspacePermission]] = {
    "administrator": frozenset(
        {
            "research.read",
            "research.write",
            "runtime.read",
            "runtime.execute",
            "mcp.use",
            "mcp.audit.read",
            "security.audit.read",
            "service.identity.manage",
            "github.projects.manage",
        }
    ),
    "operator": frozenset(
        {
            "research.read",
            "research.write",
            "runtime.read",
            "runtime.execute",
            "mcp.use",
            "github.projects.manage",
        }
    ),
    "viewer": frozenset({"research.read", "runtime.read"}),
}


class AuthorizationError(PermissionError):
    """Raised when a valid identity lacks a server-owned workspace permission."""


def require_permission(
    identity: AuthenticatedUser | AuthenticatedServiceIdentity, permission: WorkspacePermission
) -> None:
    """Allow only permissions granted by the fixed role policy."""

    if isinstance(identity, AuthenticatedServiceIdentity):
        if permission not in identity.permissions:
            raise AuthorizationError(
                "This service identity is not permitted to perform this action."
            )
        return
    if permission not in ROLE_PERMISSIONS[identity.role]:
        raise AuthorizationError("Your workspace role is not permitted to perform this action.")
