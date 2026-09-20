"""Reservation interval business operations."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ara.core.errors import DomainError
from ara.daos.assets import AssetDAO
from ara.daos.groups import GroupDAO
from ara.daos.reservations import ReservationDAO
from ara.daos.users import UserDAO
from ara.domain.models import (
    Asset,
    Group,
    Reservation,
    ReservationStatus,
    utc_now,
)
from ara.services.audit import (
    AuditAction,
    AuditContext,
    AuditService,
    AuditTargetType,
    reservation_snapshot,
)
from ara.services.authorization import AuthorizationService, EffectiveRoles


class ReservationService:
    """Own reservation interval rules and SQLite write transactions."""

    def __init__(
        self, session: AsyncSession, audit_context: AuditContext | None = None
    ) -> None:
        self.session = session
        self.reservations = ReservationDAO(session)
        self.assets = AssetDAO(session)
        self.groups = GroupDAO(session)
        self.users = UserDAO(session)
        self.audit = AuditService(session, audit_context)

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
            asset = await self._get_asset_required(asset_id)
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
            await self.session.flush()
            self.audit.record(
                action=AuditAction.RESERVATION_CREATE,
                group_id=asset.group_id,
                target_type=AuditTargetType.RESERVATION,
                target_id=reservation.id,
                before=None,
                after=reservation_snapshot(reservation),
            )
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
        await self._begin_immediate()
        try:
            now = utc_now()
            effective_starts_at = max(starts_at, now)
            self._validate_interval(effective_starts_at, ends_at)
            user = await self.users.get_by_id(user_id)
            if user is None:
                raise DomainError("user_not_found", "User not found", status_code=404)
            asset = await self._get_asset_required(asset_id)
            group = await self._get_group_required(asset.group_id)
            AuthorizationService.require_group_user(actor_roles, group.id)
            self._require_reservable(asset, group)
            await self.ensure_available(
                asset_id=asset.id, starts_at=effective_starts_at, ends_at=ends_at
            )
            reservation = Reservation(
                asset_id=asset.id,
                user_id=user.id,
                starts_at=effective_starts_at,
                ends_at=ends_at,
            )
            self.reservations.add(reservation)
            await self.session.flush()
            self.audit.record(
                action=AuditAction.RESERVATION_CREATE,
                group_id=group.id,
                target_type=AuditTargetType.RESERVATION,
                target_id=reservation.id,
                before=None,
                after=reservation_snapshot(reservation),
            )
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        return reservation

    async def list_own(
        self,
        actor_roles: EffectiveRoles,
        *,
        user_id: uuid.UUID,
        offset: int,
        limit: int,
    ) -> tuple[list[Reservation], int]:
        """List an actor's reservations with metadata only for visible assets."""
        rows, total = await self.reservations.list_for_user_with_assets(
            user_id=user_id, offset=offset, limit=limit
        )
        reservations = []
        for (
            reservation,
            name,
            asset_type,
            group_id,
            asset_archived,
            group_archived,
        ) in rows:
            # Match AssetService.get visibility while retaining the reservation
            # record for its owner. A missing historical asset or group also has
            # no display name.
            if (
                name is not None
                and group_id is not None
                and actor_roles.is_group_user(group_id)
                and (actor_roles.is_owner or not group_archived)
                and (
                    actor_roles.is_owner
                    or not asset_archived
                    or actor_roles.is_group_admin(group_id)
                )
            ):
                setattr(reservation, "asset_name", name)
                setattr(reservation, "asset_type", asset_type)
            else:
                setattr(reservation, "asset_name", None)
                setattr(reservation, "asset_type", None)
            reservations.append(reservation)
        return reservations, total

    async def extend_own(
        self,
        actor_roles: EffectiveRoles,
        *,
        actor_id: uuid.UUID,
        reservation_id: uuid.UUID,
        ends_at: datetime,
    ) -> Reservation:
        """Extend an actor's bounded, non-terminal reservation under the write lock."""
        self._validate_utc("ends_at", ends_at)
        await self._begin_immediate()
        try:
            reservation, asset = await self._reservation_with_asset(reservation_id)
            AuthorizationService.require_group_user(actor_roles, asset.group_id)
            self._require_owner(reservation, actor_id)
            self._require_nonterminal(reservation)
            if reservation.ends_at is None or ends_at <= reservation.ends_at:
                raise DomainError(
                    "reservation_not_extended",
                    "ends_at must be later than the current reservation end",
                    status_code=409,
                )
            await self.ensure_available(
                asset_id=asset.id,
                starts_at=reservation.starts_at,
                ends_at=ends_at,
                exclude_reservation_id=reservation.id,
            )
            before = reservation_snapshot(reservation)
            reservation.ends_at = ends_at
            await self.session.flush()
            self.audit.record(
                action=AuditAction.RESERVATION_EXTEND,
                group_id=asset.group_id,
                target_type=AuditTargetType.RESERVATION,
                target_id=reservation.id,
                before=before,
                after=reservation_snapshot(reservation),
            )
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        return reservation

    async def return_own(
        self,
        actor_roles: EffectiveRoles,
        *,
        actor_id: uuid.UUID,
        reservation_id: uuid.UUID,
    ) -> Reservation:
        """Return an actor's currently active reservation at the current instant."""
        await self._begin_immediate()
        try:
            reservation, asset = await self._reservation_with_asset(reservation_id)
            AuthorizationService.require_group_user(actor_roles, asset.group_id)
            self._require_owner(reservation, actor_id)
            now = utc_now()
            self._require_current(reservation, now)
            before = reservation_snapshot(reservation)
            reservation.status = ReservationStatus.RETURNED
            reservation.returned_at = now
            self._record_early_end(reservation, now)
            await self.session.flush()
            self.audit.record(
                action=AuditAction.RESERVATION_RETURN,
                group_id=asset.group_id,
                target_type=AuditTargetType.RESERVATION,
                target_id=reservation.id,
                before=before,
                after=reservation_snapshot(reservation),
            )
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        return reservation

    async def cancel(
        self,
        actor_roles: EffectiveRoles,
        *,
        actor_id: uuid.UUID,
        reservation_id: uuid.UUID,
    ) -> Reservation:
        """Cancel a future reservation as its owner or its responsible administrator."""
        await self._begin_immediate()
        try:
            reservation, asset = await self._reservation_with_asset(reservation_id)
            if reservation.user_id != actor_id:
                AuthorizationService.require_group_admin(actor_roles, asset.group_id)
            else:
                AuthorizationService.require_group_user(actor_roles, asset.group_id)
            now = utc_now()
            self._require_future(reservation, now)
            before = reservation_snapshot(reservation)
            reservation.status = ReservationStatus.CANCELLED
            reservation.cancelled_at = now
            await self.session.flush()
            self.audit.record(
                action=AuditAction.RESERVATION_CANCEL,
                group_id=asset.group_id,
                target_type=AuditTargetType.RESERVATION,
                target_id=reservation.id,
                before=before,
                after=reservation_snapshot(reservation),
            )
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        return reservation

    async def end_administratively(
        self,
        actor_roles: EffectiveRoles,
        *,
        actor_id: uuid.UUID,
        reservation_id: uuid.UUID,
    ) -> Reservation:
        """Allow an Owner or responsible Group Admin to end a current reservation."""
        await self._begin_immediate()
        try:
            reservation, asset = await self._reservation_with_asset(reservation_id)
            AuthorizationService.require_group_admin(actor_roles, asset.group_id)
            now = utc_now()
            self._require_current(reservation, now)
            before = reservation_snapshot(reservation)
            reservation.status = ReservationStatus.ENDED
            reservation.ended_at = now
            self._record_early_end(reservation, now)
            await self.session.flush()
            self.audit.record(
                action=AuditAction.RESERVATION_END,
                group_id=asset.group_id,
                target_type=AuditTargetType.RESERVATION,
                target_id=reservation.id,
                before=before,
                after=reservation_snapshot(reservation),
            )
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        return reservation

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
    def _validate_utc(name: str, value: datetime) -> None:
        if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value):
            raise DomainError(
                "reservation_timestamp_not_utc", f"{name} must be timezone-aware UTC"
            )

    async def _reservation_with_asset(
        self, reservation_id: uuid.UUID
    ) -> tuple[Reservation, Asset]:
        reservation = await self.reservations.get_by_id(reservation_id)
        if reservation is None:
            raise DomainError(
                "reservation_not_found", "Reservation not found", status_code=404
            )
        return reservation, await self._get_asset_required(reservation.asset_id)

    @staticmethod
    def _require_owner(reservation: Reservation, actor_id: uuid.UUID) -> None:
        if reservation.user_id != actor_id:
            raise DomainError(
                "authorization_denied", "Authorization denied", status_code=403
            )

    @staticmethod
    def _require_nonterminal(reservation: Reservation) -> None:
        if reservation.status is not ReservationStatus.ACTIVE:
            raise DomainError(
                "reservation_terminal",
                "Terminal reservations cannot be changed",
                status_code=409,
            )

    @classmethod
    def _require_current(cls, reservation: Reservation, now: datetime) -> None:
        cls._require_nonterminal(reservation)
        if reservation.starts_at > now or (
            reservation.ends_at is not None and reservation.ends_at <= now
        ):
            raise DomainError(
                "reservation_not_current",
                "Reservation is not currently active",
                status_code=409,
            )

    @classmethod
    def _require_future(cls, reservation: Reservation, now: datetime) -> None:
        cls._require_nonterminal(reservation)
        if reservation.starts_at <= now:
            raise DomainError(
                "reservation_not_future",
                "Only future reservations can be cancelled",
                status_code=409,
            )

    @staticmethod
    def _record_early_end(reservation: Reservation, now: datetime) -> None:
        """Keep the positive-interval constraint when ending exactly at start.

        The terminal status and returned/ended timestamp make the reservation
        unavailable from ``now``.  A zero-length interval cannot be stored due
        to the schema's strict ``ends_at > starts_at`` constraint, so its
        originally scheduled end is retained only for this exact boundary case.
        """
        if now > reservation.starts_at:
            reservation.ends_at = now

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
