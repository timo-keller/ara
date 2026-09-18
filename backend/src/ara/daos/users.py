"""Persistence access for local OIDC users."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ara.domain.models import User


class UserDAO:
    """User queries; callers own all transaction boundaries."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_oidc_identity(self, issuer: str, subject: str) -> User | None:
        """Return the user associated with an OIDC issuer and subject."""
        return await self.session.scalar(
            select(User).where(User.oidc_issuer == issuer, User.oidc_subject == subject)
        )

    def add(self, user: User) -> None:
        """Stage a new user for the service-owned transaction."""
        self.session.add(user)
