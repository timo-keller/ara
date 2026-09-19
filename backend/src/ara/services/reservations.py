"""Reservation interval business operations."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ara.core.errors import DomainError
from ara.daos.reservations import ReservationDAO
from ara.domain.models import Reservation


class ReservationService:
    """Own reservation interval rules and SQLite write transactions."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.reservations = ReservationDAO(session)

    async def create(
        self,
        *,
        asset_id: uuid.UUID,
        user_id: uuid.UUID,
        starts_at: datetime,
        ends_at: datetime | None,
    ) -> Reservation:
        """Create a reservation after atomically checking its availability.

        ``BEGIN IMMEDIATE`` obtains SQLite's one writer slot before the read.
        That makes the read/check/write sequence safe for ARA's documented
        single-process deployment; it is not a substitute for a multi-process
        exclusion constraint.
        """
        self._validate_interval(starts_at, ends_at)
        await self.session.execute(text("BEGIN IMMEDIATE"))
        try:
            await self.ensure_available(
                asset_id=asset_id, starts_at=starts_at, ends_at=ends_at
            )
            reservation = Reservation(
                asset_id=asset_id,
                user_id=user_id,
                starts_at=starts_at,
                ends_at=ends_at,
            )
            self.reservations.add(reservation)
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        await self.session.refresh(reservation)
        return reservation

    async def ensure_available(
        self,
        *,
        asset_id: uuid.UUID,
        starts_at: datetime,
        ends_at: datetime | None,
        exclude_reservation_id: uuid.UUID | None = None,
    ) -> None:
        """Raise a domain conflict if an active interval overlaps this one.

        Lifecycle operations reuse this after acquiring their write transaction;
        ``exclude_reservation_id`` prevents an update from conflicting with
        itself.
        """
        self._validate_interval(starts_at, ends_at)
        if ends_at is None:
            conflict = await self.reservations.get_open_ended_conflict(
                asset_id=asset_id,
                starts_at=starts_at,
                exclude_reservation_id=exclude_reservation_id,
            )
        else:
            conflict = await self.reservations.get_bounded_conflict(
                asset_id=asset_id,
                starts_at=starts_at,
                ends_at=ends_at,
                exclude_reservation_id=exclude_reservation_id,
            )
        if conflict is not None:
            raise DomainError(
                "reservation_conflict",
                "The asset is already reserved for the requested interval",
                status_code=409,
            )

    @staticmethod
    def _validate_interval(starts_at: datetime, ends_at: datetime | None) -> None:
        """Require explicit UTC instants and a positive bounded interval."""
        for name, value in (("starts_at", starts_at), ("ends_at", ends_at)):
            if value is not None and (
                value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value)
            ):
                raise DomainError(
                    "reservation_timestamp_not_utc",
                    f"{name} must be timezone-aware UTC",
                )
        if ends_at is not None and ends_at <= starts_at:
            raise DomainError(
                "reservation_invalid_interval",
                "ends_at must be after starts_at",
            )
