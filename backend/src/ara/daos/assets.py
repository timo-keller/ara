"""Persistence queries for ARA assets."""

import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ara.domain.models import Asset, Reservation, ReservationStatus, User, utc_now


class AssetDAO:
    """Asset queries; callers own authorization and transaction boundaries."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def add(self, asset: Asset) -> None:
        """Stage an asset for the caller's service transaction."""
        self.session.add(asset)

    async def get_by_id(self, asset_id: uuid.UUID) -> Asset | None:
        """Return an asset regardless of its archival state."""
        return await self.session.get(Asset, asset_id)

    async def list_assets(
        self,
        *,
        group_ids: set[uuid.UUID] | None,
        group_id: uuid.UUID | None,
        asset_type: str | None,
        text: str | None,
        availability: str | None,
        archived: bool | None,
        offset: int,
        limit: int,
    ) -> tuple[list[tuple[Asset, str | None]], int]:
        """Return a stable page and total without applying access rules."""
        filters = []
        if group_ids is not None:
            filters.append(Asset.group_id.in_(group_ids))
        if group_id is not None:
            filters.append(Asset.group_id == group_id)
        if asset_type is not None:
            filters.append(Asset.asset_type == asset_type)
        if text is not None:
            pattern = f"%{text}%"
            filters.append(
                or_(Asset.name.ilike(pattern), Asset.description.ilike(pattern))
            )
        now = utc_now()
        # Keep this correlated lookup in the catalogue query so the caller never
        # needs to request reservations for individual assets.  A scalar subquery
        # also keeps an unexpected duplicate active reservation from duplicating
        # an asset row.
        reserved_by_display_name = (
            select(
                func.coalesce(
                    func.nullif(func.trim(User.display_name), ""),
                    func.nullif(func.trim(User.email), ""),
                    "Unknown user",
                )
            )
            .select_from(Reservation)
            .join(User, User.id == Reservation.user_id)
            .where(
                Reservation.asset_id == Asset.id,
                Reservation.status == ReservationStatus.ACTIVE,
                Reservation.starts_at <= now,
                or_(Reservation.ends_at.is_(None), Reservation.ends_at > now),
            )
            .order_by(Reservation.id)
            .limit(1)
            .scalar_subquery()
        )
        reserved_now = reserved_by_display_name.is_not(None)
        if availability is not None:
            filters.append(
                reserved_now if availability == "reserved" else ~reserved_now
            )
        if archived is True:
            filters.append(Asset.archived_at.is_not(None))
        elif archived is False:
            filters.append(Asset.archived_at.is_(None))
        statement = select(
            Asset,
            reserved_by_display_name.label("reserved_by_display_name"),
        ).where(*filters)
        total = await self.session.scalar(
            select(func.count()).select_from(statement.subquery())
        )
        result = await self.session.execute(
            statement.order_by(Asset.name, Asset.id).offset(offset).limit(limit)
        )
        return [(asset, holder) for asset, holder in result], total or 0
