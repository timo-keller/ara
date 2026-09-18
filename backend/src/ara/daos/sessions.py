"""Persistence access for application sessions."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ara.domain.models import ApplicationSession


class ApplicationSessionDAO:
    """Application-session queries; callers own all transaction boundaries."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, session_id: uuid.UUID) -> ApplicationSession | None:
        """Load a session with its user for authentication dependencies."""
        return await self.session.get(
            ApplicationSession,
            session_id,
            options=[selectinload(ApplicationSession.user)],
        )

    def add(self, application_session: ApplicationSession) -> None:
        """Stage a session for the service-owned transaction."""
        self.session.add(application_session)
