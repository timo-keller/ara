"""Authentication business rules and application-session transactions."""

import hashlib
import secrets
import uuid
from collections.abc import Mapping
from datetime import timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from ara.daos.sessions import ApplicationSessionDAO
from ara.daos.users import UserDAO
from ara.domain.models import ApplicationSession, User, utc_now

SESSION_TTL_SECONDS = 8 * 60 * 60
SESSION_RENEWAL_WINDOW_SECONDS = 60 * 60


def csrf_token_hash(token: str) -> str:
    """Store only a one-way representation of a high-entropy CSRF token."""
    return hashlib.sha256(token.encode()).hexdigest()


class AuthenticationService:
    """Own authentication state changes and their transaction boundaries."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserDAO(session)
        self.sessions = ApplicationSessionDAO(session)

    async def upsert_oidc_user(self, claims: Mapping[str, Any]) -> User:
        """Synchronize a local OIDC user in its own service transaction."""
        user = await self._stage_oidc_user(claims)
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def _stage_oidc_user(self, claims: Mapping[str, Any]) -> User:
        """Apply OIDC profile changes without committing the caller's transaction."""
        issuer, subject = str(claims["iss"]).rstrip("/"), str(claims["sub"])
        user = await self.users.get_by_oidc_identity(issuer, subject)
        name = claims.get("name") or claims.get("preferred_username")
        email = claims.get("email")
        display_name = (
            name.strip()[:255] if isinstance(name, str) and name.strip() else None
        )
        safe_email = (
            email.strip()[:320] if isinstance(email, str) and email.strip() else None
        )
        if user is None:
            user = User(
                oidc_issuer=issuer,
                oidc_subject=subject,
                display_name=display_name,
                email=safe_email,
                last_login_at=utc_now(),
            )
            self.users.add(user)
        else:
            user.display_name, user.email, user.last_login_at = (
                display_name,
                safe_email,
                utc_now(),
            )
        return user

    async def create_oidc_session(
        self, claims: Mapping[str, Any]
    ) -> tuple[ApplicationSession, str]:
        """Atomically synchronize an OIDC user and create its browser session."""
        user = await self._stage_oidc_user(claims)
        await self.session.flush()
        csrf_token, now = secrets.token_urlsafe(32), utc_now()
        application_session = ApplicationSession(
            user_id=user.id,
            csrf_token_hash=csrf_token_hash(csrf_token),
            expires_at=now + timedelta(seconds=SESSION_TTL_SECONDS),
        )
        self.sessions.add(application_session)
        await self.session.commit()
        await self.session.refresh(application_session)
        return application_session, csrf_token

    async def create_session(self, user: User) -> tuple[ApplicationSession, str]:
        csrf_token, now = secrets.token_urlsafe(32), utc_now()
        application_session = ApplicationSession(
            user_id=user.id,
            csrf_token_hash=csrf_token_hash(csrf_token),
            expires_at=now + timedelta(seconds=SESSION_TTL_SECONDS),
        )
        self.sessions.add(application_session)
        await self.session.commit()
        await self.session.refresh(application_session)
        return application_session, csrf_token

    async def get_live_session(
        self, session_id: uuid.UUID
    ) -> tuple[ApplicationSession | None, bool]:
        application_session = await self.sessions.get_by_id(session_id)
        now = utc_now()
        if (
            application_session is None
            or application_session.revoked_at is not None
            or application_session.expires_at <= now
        ):
            return None, False
        renewed = application_session.expires_at - now <= timedelta(
            seconds=SESSION_RENEWAL_WINDOW_SECONDS
        )
        if renewed:
            application_session.expires_at = now + timedelta(
                seconds=SESSION_TTL_SECONDS
            )
            application_session.renewed_at = now
            await self.session.commit()
        return application_session, renewed

    async def revoke_session(self, application_session: ApplicationSession) -> None:
        application_session.revoked_at = utc_now()
        await self.session.commit()
