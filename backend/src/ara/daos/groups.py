"""Persistence queries for ARA groups."""

import uuid

from sqlalchemy import exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ara.domain.models import Asset, Group, Reservation, ReservationStatus


class GroupDAO:
    """Group queries; callers own authorization and transaction boundaries."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def add(self, group: Group) -> None:
        """Stage a group for the caller's service transaction."""
        self.session.add(group)

    async def get_by_id(self, group_id: uuid.UUID) -> Group | None:
        """Return a group regardless of its archival state."""
        return await self.session.get(Group, group_id)

    async def list_groups(
        self,
        *,
        group_ids: set[uuid.UUID] | None,
        archived: bool | None,
        offset: int,
        limit: int,
    ) -> tuple[list[Group], int]:
        """Return a stable page and its total without applying access rules."""
        filters = []
        if group_ids is not None:
            filters.append(Group.id.in_(group_ids))
        if archived is True:
            filters.append(Group.archived_at.is_not(None))
        elif archived is False:
            filters.append(Group.archived_at.is_(None))
        statement = select(Group).where(*filters)
        total = await self.session.scalar(
            select(func.count()).select_from(statement.subquery())
        )
        result = await self.session.scalars(
            statement.order_by(Group.name, Group.id).offset(offset).limit(limit)
        )
        return list(result), total or 0

    async def has_unresolved_reservations(self, group_id: uuid.UUID) -> bool:
        """Whether an active reservation on any group asset blocks archival."""
        statement = select(
            exists().where(
                Asset.group_id == group_id,
                Reservation.asset_id == Asset.id,
                Reservation.status == ReservationStatus.ACTIVE,
            )
        )
        return bool(await self.session.scalar(statement))
