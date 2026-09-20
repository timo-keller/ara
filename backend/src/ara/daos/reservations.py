"""Persistence queries for ARA reservations."""

import uuid
from datetime import datetime

from sqlalchemy import and_, func, or_, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from ara.domain.models import Asset, Group, Reservation, ReservationStatus

ReservationAssetRow = tuple[
    Reservation, str | None, str | None, uuid.UUID | None, bool, bool
]


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
        self,
        *,
        user_id: uuid.UUID,
        offset: int,
        limit: int,
        now: datetime,
        is_owner: bool,
        group_ids: tuple[uuid.UUID, ...],
        admin_group_ids: tuple[uuid.UUID, ...],
        asset_name: str | None = None,
        asset_type: str | None = None,
        timespan_from: datetime | None = None,
        timespan_to: datetime | None = None,
        lifecycle: tuple[str, ...] = (),
    ) -> tuple[list[ReservationAssetRow], int]:
        """Return one user's reservations with their asset visibility details."""
        filters = [Reservation.user_id == user_id]
        if timespan_to is not None:
            filters.append(Reservation.starts_at <= timespan_to)
        if timespan_from is not None:
            filters.append(
                or_(Reservation.ends_at.is_(None), Reservation.ends_at >= timespan_from)
            )
        if lifecycle:
            categories = []
            if "current" in lifecycle:
                categories.append(
                    and_(
                        Reservation.status == ReservationStatus.ACTIVE,
                        Reservation.starts_at <= now,
                        or_(Reservation.ends_at.is_(None), Reservation.ends_at > now),
                    )
                )
            if "future" in lifecycle:
                categories.append(
                    and_(
                        Reservation.status == ReservationStatus.ACTIVE,
                        Reservation.starts_at > now,
                    )
                )
            if "expired" in lifecycle:
                categories.append(
                    and_(
                        Reservation.status == ReservationStatus.ACTIVE,
                        Reservation.ends_at.is_not(None),
                        Reservation.ends_at <= now,
                    )
                )
            for name, status in (
                ("returned", ReservationStatus.RETURNED),
                ("cancelled", ReservationStatus.CANCELLED),
                ("ended", ReservationStatus.ENDED),
            ):
                if name in lifecycle:
                    categories.append(Reservation.status == status)
            filters.append(or_(*categories))
        if asset_name is not None or asset_type is not None:
            # Metadata predicates use precisely the policy used to expose names below.
            visible = (
                true()
                if is_owner
                else and_(
                    Group.id.in_(group_ids),
                    Group.archived_at.is_(None),
                    or_(Asset.archived_at.is_(None), Group.id.in_(admin_group_ids)),
                )
            )
            filters.append(visible)
            if asset_name is not None:
                filters.append(Asset.name.ilike(f"%{asset_name}%"))
            if asset_type is not None:
                filters.append(Asset.asset_type == asset_type)
        statement = (
            select(Reservation)
            .outerjoin(Asset, Reservation.asset_id == Asset.id)
            .outerjoin(Group, Asset.group_id == Group.id)
            .where(*filters)
        )
        total = await self.session.scalar(
            select(func.count()).select_from(statement.subquery())
        )
        result = await self.session.execute(
            select(
                Reservation,
                Asset.name,
                Asset.asset_type,
                Group.id,
                Asset.archived_at.is_not(None),
                Group.archived_at.is_not(None),
            )
            .outerjoin(Asset, Reservation.asset_id == Asset.id)
            .outerjoin(Group, Asset.group_id == Group.id)
            .where(*filters)
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
