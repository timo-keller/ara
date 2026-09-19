"""Business operations for persistent reservation reminders."""

import uuid
from datetime import timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ara.core.errors import DomainError
from ara.daos.notifications import NotificationDAO
from ara.domain.models import Notification, utc_now


class NotificationService:
    """Own notification authorization and transaction boundaries."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.notifications = NotificationDAO(session)

    async def list_own(
        self, *, user_id: uuid.UUID, offset: int, limit: int
    ) -> tuple[list[Notification], int]:
        return await self.notifications.list_for_user(
            user_id=user_id, offset=offset, limit=limit
        )

    async def mark_read(
        self, *, user_id: uuid.UUID, notification_id: uuid.UUID
    ) -> Notification:
        """Mark one owned notification read, retaining its original timestamp."""
        notification = await self.notifications.get_for_user(
            notification_id=notification_id, user_id=user_id
        )
        if notification is None:
            raise DomainError(
                "notification_not_found", "Notification not found", status_code=404
            )
        if notification.read_at is None:
            notification.read_at = utc_now()
            await self.session.commit()
        return notification

    async def generate_due_reminders(self, offsets_minutes: tuple[int, ...]) -> int:
        """Persist every due reminder, including ones missed while the process was down.

        The persisted key is ``(reservation_id, kind, scheduled_for)``.  Here
        ``kind`` includes the configured offset and ``scheduled_for`` is the
        reservation end minus that offset, making every reminder stable across
        repeated runs and configuration restarts.
        """
        now = utc_now()
        candidates = await self.notifications.due_reservations(
            due_before=now + timedelta(minutes=max(offsets_minutes))
        )
        created = 0
        try:
            for reservation in candidates:
                # The DAO excludes open-ended and terminal reservations.  The
                # second condition is what makes overdue reminders catch up.
                assert reservation.ends_at is not None
                for offset in offsets_minutes:
                    scheduled_for = reservation.ends_at - timedelta(minutes=offset)
                    if scheduled_for > now:
                        continue
                    nested = await self.session.begin_nested()
                    try:
                        self.notifications.add(
                            Notification(
                                user_id=reservation.user_id,
                                reservation_id=reservation.id,
                                kind=f"reservation_end_reminder:{offset}",
                                title="Reservation ending",
                                body=(
                                    "Your reservation is scheduled to end at "
                                    f"{reservation.ends_at.isoformat()}"
                                ),
                                scheduled_for=scheduled_for,
                            )
                        )
                        await self.session.flush()
                    except IntegrityError:
                        await nested.rollback()
                    else:
                        await nested.commit()
                        created += 1
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        return created
