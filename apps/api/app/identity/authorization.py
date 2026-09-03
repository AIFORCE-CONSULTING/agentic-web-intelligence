"""Code-owned workspace permissions; request text never grants authority."""

from typing import Literal

from app.identity.contracts import AuthenticatedUser, WorkspaceRole

WorkspacePermission = Literal[
    "research.read",
    "research.write",
    "runtime.read",
    "mcp.use",
    "mcp.audit.read",
    "security.audit.read",
]

ROLE_PERMISSIONS: dict[WorkspaceRole, frozenset[WorkspacePermission]] = {
    "administrator": frozenset(
        {
            "research.read",
            "research.write",
            "runtime.read",
            "mcp.use",
            "mcp.audit.read",
            "security.audit.read",
        }
    ),
    "operator": frozenset({"research.read", "research.write", "runtime.read", "mcp.use"}),
    "viewer": frozenset({"research.read", "runtime.read"}),
}


class AuthorizationError(PermissionError):
    """Raised when a valid identity lacks a server-owned workspace permission."""


def require_permission(user: AuthenticatedUser, permission: WorkspacePermission) -> None:
    """Allow only permissions granted by the fixed role policy."""

    if permission not in ROLE_PERMISSIONS[user.role]:
        raise AuthorizationError("Your workspace role is not permitted to perform this action.")
