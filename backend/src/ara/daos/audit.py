"""Persistence operations for append-only audit events."""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import String, and_, case, cast, delete, func, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from ara.domain.models import Asset, AuditEvent, Group, Reservation, RoleMapping, User


@dataclass(frozen=True)
class AuditEventResult:
    """An audit event with display values resolved in the list query."""

    event: AuditEvent
    actor_name: str | None
    target_name: str | None


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
        actor_id: str | None,
        action: Sequence[str] | None,
        target_type: Sequence[str] | None,
        target_id: str | None,
        created_at_from: datetime | None,
        created_at_to: datetime | None,
        offset: int,
        limit: int,
    ) -> tuple[list[AuditEventResult], int]:
        """Return a stable filtered page without applying authorization policy."""
        actor = aliased(User)
        asset = aliased(Asset)
        target_group = aliased(Group)
        reservation = aliased(Reservation)
        reservation_asset = aliased(Asset)
        role_mapping = aliased(RoleMapping)

        target_name = case(
            (AuditEvent.target_type == "asset", asset.name),
            (AuditEvent.target_type == "group", target_group.name),
            (
                AuditEvent.target_type == "reservation",
                literal("Reservation for ") + reservation_asset.name,
            ),
            (
                AuditEvent.target_type == "role_mapping",
                literal("Role mapping: ") + role_mapping.expression,
            ),
            else_=None,
        ).label("target_name")
        statement = (
            select(AuditEvent, actor.display_name.label("actor_name"), target_name)
            .outerjoin(actor, AuditEvent.actor_id == actor.id)
            .outerjoin(
                asset,
                and_(
                    AuditEvent.target_type == "asset",
                    func.replace(cast(asset.id, String), "-", "")
                    == func.replace(AuditEvent.target_id, "-", ""),
                ),
            )
            .outerjoin(
                target_group,
                and_(
                    AuditEvent.target_type == "group",
                    func.replace(cast(target_group.id, String), "-", "")
                    == func.replace(AuditEvent.target_id, "-", ""),
                ),
            )
            .outerjoin(
                reservation,
                and_(
                    AuditEvent.target_type == "reservation",
                    func.replace(cast(reservation.id, String), "-", "")
                    == func.replace(AuditEvent.target_id, "-", ""),
                ),
            )
            .outerjoin(reservation_asset, reservation.asset_id == reservation_asset.id)
            .outerjoin(
                role_mapping,
                and_(
                    AuditEvent.target_type == "role_mapping",
                    func.replace(cast(role_mapping.id, String), "-", "")
                    == func.replace(AuditEvent.target_id, "-", ""),
                ),
            )
        )
        filters = []
        if group_ids is not None:
            filters.append(AuditEvent.group_id.in_(group_ids))
        if group_id is not None:
            filters.append(AuditEvent.group_id == group_id)
        if actor_id is not None:
            actor_identifier = actor_id.replace("-", "")
            filters.append(
                or_(
                    func.replace(cast(AuditEvent.actor_id, String), "-", "").ilike(
                        f"%{actor_identifier}%"
                    ),
                    actor.display_name.ilike(f"%{actor_id}%"),
                )
            )
        if action:
            filters.append(AuditEvent.action.in_(action))
        if target_type:
            filters.append(AuditEvent.target_type.in_(target_type))
        if target_id is not None:
            filters.append(
                or_(
                    AuditEvent.target_id.ilike(f"%{target_id}%"),
                    target_name.ilike(f"%{target_id}%"),
                )
            )
        if created_at_from is not None:
            filters.append(AuditEvent.created_at >= created_at_from)
        if created_at_to is not None:
            filters.append(AuditEvent.created_at <= created_at_to)

        total = await self.session.scalar(
            select(func.count()).select_from(
                statement.with_only_columns(AuditEvent.id).where(*filters).subquery()
            )
        )
        rows = await self.session.execute(
            statement.where(*filters)
            .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
            .offset(offset)
            .limit(limit)
        )
        return [AuditEventResult(*row) for row in rows], total or 0
