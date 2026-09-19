"""Persistence queries for in-application notifications."""

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ara.domain.models import Notification, Reservation, ReservationStatus


class NotificationDAO:
    """Notification persistence without authorization or transaction policy."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def add(self, notification: Notification) -> None:
        self.session.add(notification)

    async def list_for_user(
        self, *, user_id: uuid.UUID, offset: int, limit: int
    ) -> tuple[list[Notification], int]:
        statement = select(Notification).where(Notification.user_id == user_id)
        total = await self.session.scalar(
            select(func.count()).select_from(statement.subquery())
        )
        result = await self.session.scalars(
            statement.order_by(Notification.created_at.desc(), Notification.id.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result), total or 0

    async def get_for_user(
        self, *, notification_id: uuid.UUID, user_id: uuid.UUID
    ) -> Notification | None:
        return await self.session.scalar(
            select(Notification).where(
                Notification.id == notification_id, Notification.user_id == user_id
            )
        )

    async def due_reservations(self, *, due_before: datetime) -> list[Reservation]:
        """Return bounded active reservations ending at or before ``due_before``."""
        result = await self.session.scalars(
            select(Reservation).where(
                Reservation.status == ReservationStatus.ACTIVE,
                Reservation.ends_at.is_not(None),
                Reservation.ends_at <= due_before,
            )
        )
        return list(result)
