"""Security-sensitive local identity service with an explicit future OIDC boundary."""

import hmac
import secrets
from uuid import UUID

from pwdlib import PasswordHash

from app.identity.contracts import AuthenticatedUser
from app.identity.store import IdentityStore

SESSION_COOKIE_NAME = "platform_session"
_password_hash = PasswordHash.recommended()


class AuthenticationError(ValueError):
    """Raised for non-enumerating local authentication failures."""


class IdentityService:
    """Trusted server-side local authentication; agents never receive this service."""

    def __init__(self, store: IdentityStore, bootstrap_secret: str | None) -> None:
        self._store = store
        self._bootstrap_secret = bootstrap_secret

    async def bootstrap_admin(
        self, bootstrap_secret: str, email: str, password: str
    ) -> tuple[AuthenticatedUser, str]:
        if not self._bootstrap_secret or not hmac.compare_digest(
            bootstrap_secret, self._bootstrap_secret
        ):
            raise AuthenticationError("Local administrator bootstrap is not authorized.")
        user = await self._store.create_bootstrap_admin(email, _password_hash.hash(password))
        return user, await self._new_session(user.id)

    async def sign_in(self, email: str, password: str) -> tuple[AuthenticatedUser, str]:
        credential = await self._store.authenticate_local(email)
        if credential is None or not _password_hash.verify(password, credential[1]):
            raise AuthenticationError("Invalid email or password.")
        token = await self._new_session(credential[0])
        user = await self._store.get_session_user(token)
        assert user is not None
        return user, token

    async def current_user(self, token: str | None) -> AuthenticatedUser | None:
        return await self._store.get_session_user(token) if token else None

    async def sign_out(self, token: str | None) -> None:
        if token:
            await self._store.revoke_session(token)

    async def _new_session(self, user_id: UUID) -> str:
        token = secrets.token_urlsafe(32)
        await self._store.create_session(user_id, token)
        return token
