"""Persistence queries for ARA reservations."""

import uuid
from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ara.domain.models import Reservation, ReservationStatus


class ReservationDAO:
    """Reservation queries; callers own policy and transaction boundaries."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def add(self, reservation: Reservation) -> None:
        """Stage a reservation for the caller's service transaction."""
        self.session.add(reservation)

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
