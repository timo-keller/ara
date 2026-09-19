"""Persistence operations for append-only audit events."""

from sqlalchemy.ext.asyncio import AsyncSession

from ara.domain.models import AuditEvent


class AuditDAO:
    """Stage audit rows; transaction ownership remains with services."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def add(self, event: AuditEvent) -> None:
        """Stage an event in the caller's transaction."""
        self.session.add(event)
