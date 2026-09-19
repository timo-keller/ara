"""Reservation interval business operations."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ara.core.errors import DomainError
from ara.daos.assets import AssetDAO
from ara.daos.groups import GroupDAO
from ara.daos.reservations import ReservationDAO
from ara.daos.users import UserDAO
from ara.domain.models import Asset, Group, Reservation, utc_now
from ara.services.authorization import AuthorizationService, EffectiveRoles


class ReservationService:
    """Own reservation interval rules and SQLite write transactions."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.reservations = ReservationDAO(session)
        self.assets = AssetDAO(session)
        self.groups = GroupDAO(session)
        self.users = UserDAO(session)

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
        await self._begin_immediate()
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
        return reservation

    async def create_for_current_user(
        self,
        actor_roles: EffectiveRoles,
        *,
        asset_id: uuid.UUID,
        user_id: uuid.UUID,
        starts_at: datetime,
        ends_at: datetime | None,
    ) -> Reservation:
        """Create a current user's reservation with all checks in one write lock."""
        self._validate_interval(starts_at, ends_at)
        self._validate_current_user_start(starts_at)
        await self._begin_immediate()
        try:
            user = await self.users.get_by_id(user_id)
            if user is None:
                raise DomainError("user_not_found", "User not found", status_code=404)
            asset = await self._get_asset_required(asset_id)
            group = await self._get_group_required(asset.group_id)
            AuthorizationService.require_group_user(actor_roles, group.id)
            self._require_reservable(asset, group)
            await self.ensure_available(
                asset_id=asset.id, starts_at=starts_at, ends_at=ends_at
            )
            reservation = Reservation(
                asset_id=asset.id,
                user_id=user.id,
                starts_at=starts_at,
                ends_at=ends_at,
            )
            self.reservations.add(reservation)
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        return reservation

    async def list_own(
        self, *, user_id: uuid.UUID, offset: int, limit: int
    ) -> tuple[list[Reservation], int]:
        """List reservations belonging only to the authenticated user."""
        return await self.reservations.list_for_user(
            user_id=user_id, offset=offset, limit=limit
        )

    async def list_asset_schedule(
        self,
        actor_roles: EffectiveRoles,
        *,
        asset_id: uuid.UUID,
        offset: int,
        limit: int,
    ) -> tuple[list[Reservation], int]:
        """List an accessible asset's active schedule without cross-group leakage."""
        asset = await self._get_asset_required(asset_id)
        AuthorizationService.require_group_user(actor_roles, asset.group_id)
        return await self.reservations.list_active_for_asset(
            asset_id=asset.id, offset=offset, limit=limit
        )

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

    @staticmethod
    def _validate_current_user_start(starts_at: datetime) -> None:
        """Reject historical self-service reservations while allowing immediate use.

        A short grace period accounts for a browser's current timestamp becoming
        slightly stale while its request is in transit.
        """
        if starts_at < utc_now() - timedelta(minutes=1):
            raise DomainError(
                "reservation_start_in_past",
                "starts_at must be now or in the future",
            )

    async def _begin_immediate(self) -> None:
        """Start a SQLite write transaction without nesting request reads."""
        # Authentication and role resolution share the request session and can
        # open SQLAlchemy's implicit read transaction. It contains no mutation,
        # so end it before acquiring the write lock; asset/user validation and
        # interval conflict checking below then occur inside that one lock.
        if self.session.in_transaction():
            await self.session.rollback()
        await self.session.execute(text("BEGIN IMMEDIATE"))

    async def _get_asset_required(self, asset_id: uuid.UUID) -> Asset:
        asset = await self.assets.get_by_id(asset_id)
        if asset is None:
            raise DomainError("asset_not_found", "Asset not found", status_code=404)
        return asset

    async def _get_group_required(self, group_id: uuid.UUID) -> Group:
        group = await self.groups.get_by_id(group_id)
        if group is None:
            raise DomainError("group_not_found", "Group not found", status_code=404)
        return group

    @staticmethod
    def _require_reservable(asset: Asset, group: Group) -> None:
        if group.archived_at is not None:
            raise DomainError("group_archived", "Group is archived", status_code=409)
        if asset.archived_at is not None:
            raise DomainError("asset_archived", "Asset is archived", status_code=409)
