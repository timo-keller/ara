"""Persistence operations for append-only audit events."""

import uuid
from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ara.domain.models import AuditEvent


class AuditDAO:
    """Stage audit rows; transaction ownership remains with services."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def add(self, event: AuditEvent) -> None:
        """Stage an event in the caller's transaction."""
        self.session.add(event)

    async def delete_events_before(self, cutoff: datetime, batch_size: int) -> int:
        """Delete at most ``batch_size`` events strictly older than ``cutoff``.

        The caller owns the transaction so retention cleanup can commit each
        bounded batch independently.
        """
        event_ids = list(
            await self.session.scalars(
                select(AuditEvent.id)
                .where(AuditEvent.created_at < cutoff)
                .order_by(AuditEvent.created_at, AuditEvent.id)
                .limit(batch_size)
            )
        )
        if not event_ids:
            return 0
        await self.session.execute(
            delete(AuditEvent).where(AuditEvent.id.in_(event_ids))
        )
        return len(event_ids)

    async def list_events(
        self,
        *,
        group_ids: set[uuid.UUID] | None,
        group_id: uuid.UUID | None,
        actor_id: uuid.UUID | None,
        action: str | None,
        target_type: str | None,
        target_id: str | None,
        created_at_from: datetime | None,
        created_at_to: datetime | None,
        offset: int,
        limit: int,
    ) -> tuple[list[AuditEvent], int]:
        """Return a stable filtered page without applying authorization policy."""
        filters = []
        if group_ids is not None:
            filters.append(AuditEvent.group_id.in_(group_ids))
        if group_id is not None:
            filters.append(AuditEvent.group_id == group_id)
        if actor_id is not None:
            filters.append(AuditEvent.actor_id == actor_id)
        if action is not None:
            filters.append(AuditEvent.action == action)
        if target_type is not None:
            filters.append(AuditEvent.target_type == target_type)
        if target_id is not None:
            filters.append(AuditEvent.target_id == target_id)
        if created_at_from is not None:
            filters.append(AuditEvent.created_at >= created_at_from)
        if created_at_to is not None:
            filters.append(AuditEvent.created_at <= created_at_to)

        statement = select(AuditEvent).where(*filters)
        total = await self.session.scalar(
            select(func.count()).select_from(statement.subquery())
        )
        events = await self.session.scalars(
            statement.order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(events), total or 0
