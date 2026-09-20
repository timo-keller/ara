"""Persistence queries for ARA reservations."""

import uuid
from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ara.domain.models import Asset, Group, Reservation, ReservationStatus


class ReservationDAO:
    """Reservation queries; callers own policy and transaction boundaries."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def add(self, reservation: Reservation) -> None:
        """Stage a reservation for the caller's service transaction."""
        self.session.add(reservation)

    async def get_by_id(self, reservation_id: uuid.UUID) -> Reservation | None:
        """Return a reservation by identifier without applying access policy."""
        return await self.session.get(Reservation, reservation_id)

    async def list_for_user_with_assets(
        self, *, user_id: uuid.UUID, offset: int, limit: int
    ) -> tuple[list[tuple[Reservation, str | None, uuid.UUID | None, bool, bool]], int]:
        """Return one user's reservations with their asset visibility details."""
        statement = select(Reservation).where(Reservation.user_id == user_id)
        total = await self.session.scalar(
            select(func.count()).select_from(statement.subquery())
        )
        result = await self.session.execute(
            select(
                Reservation,
                Asset.name,
                Group.id,
                Asset.archived_at.is_not(None),
                Group.archived_at.is_not(None),
            )
            .outerjoin(Asset, Reservation.asset_id == Asset.id)
            .outerjoin(Group, Asset.group_id == Group.id)
            .where(Reservation.user_id == user_id)
            .order_by(Reservation.starts_at.desc(), Reservation.id.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.tuples()), total or 0

    async def list_active_for_asset(
        self, *, asset_id: uuid.UUID, offset: int, limit: int
    ) -> tuple[list[Reservation], int]:
        """Return an asset's active schedule in stable chronological order."""
        statement = select(Reservation).where(
            Reservation.asset_id == asset_id,
            Reservation.status == ReservationStatus.ACTIVE,
        )
        total = await self.session.scalar(
            select(func.count()).select_from(statement.subquery())
        )
        result = await self.session.scalars(
            statement.order_by(Reservation.starts_at, Reservation.id)
            .offset(offset)
            .limit(limit)
        )
        return list(result), total or 0

    async def get_bounded_conflict(
        self,
        *,
        asset_id: uuid.UUID,
        starts_at: datetime,
        ends_at: datetime,
        exclude_reservation_id: uuid.UUID | None = None,
    ) -> Reservation | None:
        """Return an active interval overlapping a bounded requested interval."""
        filters = [
            Reservation.asset_id == asset_id,
            Reservation.status == ReservationStatus.ACTIVE,
            Reservation.starts_at < ends_at,
            or_(Reservation.ends_at.is_(None), starts_at < Reservation.ends_at),
        ]
        if exclude_reservation_id is not None:
            filters.append(Reservation.id != exclude_reservation_id)
        return await self.session.scalar(select(Reservation).where(*filters).limit(1))

    async def get_open_ended_conflict(
        self,
        *,
        asset_id: uuid.UUID,
        starts_at: datetime,
        exclude_reservation_id: uuid.UUID | None = None,
    ) -> Reservation | None:
        """Return an active interval overlapping an unbounded requested interval."""
        filters = [
            Reservation.asset_id == asset_id,
            Reservation.status == ReservationStatus.ACTIVE,
            or_(Reservation.ends_at.is_(None), starts_at < Reservation.ends_at),
        ]
        if exclude_reservation_id is not None:
            filters.append(Reservation.id != exclude_reservation_id)
        return await self.session.scalar(select(Reservation).where(*filters).limit(1))
