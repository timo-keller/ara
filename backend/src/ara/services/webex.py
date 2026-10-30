"""Transactional notification production and durable, bounded Webex dispatch."""

import re
import uuid
from datetime import datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ara.core.config import Settings, get_settings
from ara.core.errors import DomainError
from ara.daos.webex import WebexDAO
from ara.domain.models import (
    Asset,
    Group,
    Reservation,
    ReservationStatus,
    User,
    WebexDelivery,
    utc_now,
)
from ara.infrastructure.webex import WebexClient
from ara.services.authorization import AuthorizationService, EffectiveRoles

START_CATCH_UP = timedelta(hours=1)
REMINDER_CATCH_UP = timedelta(hours=24)
ROOM_DELIVERY_RETENTION = timedelta(hours=1)
PERSONAL_DELIVERY_RETENTION = timedelta(days=30)
MAX_ATTEMPTS = 6
DISPATCH_BATCH = 20


def escape_markdown(value: str) -> str:
    return re.sub(r"([\\`*_\[\]<>])", r"\\\1", value)


class WebexService:
    def __init__(self, session: AsyncSession, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.deliveries = WebexDAO(session)

    async def enqueue_event(
        self,
        reservation: Reservation,
        kind: str,
        scheduled_for: datetime,
        *,
        personal: bool = False,
        room: bool = False,
        offset: int | None = None,
    ) -> None:
        """Stage messages beside domain mutations; never commit here."""
        if self.settings.webex_bot_token is None:
            return
        asset = await self.session.get(Asset, reservation.asset_id)
        user = await self.session.get(User, reservation.user_id)
        assert asset is not None and user is not None
        group = await self.session.get(Group, asset.group_id)
        assert group is not None
        key = f"{reservation.id}:{kind}"
        if kind == "end_reminder":
            assert reservation.ends_at is not None
            key += f":{reservation.ends_at.isoformat()}:{offset}"
            description = (
                "Reservation end reminder: {asset} is scheduled to end at "
                f"{reservation.ends_at.isoformat()}."
            )
        elif kind == "start":
            description = (
                "Reservation started: {asset} at "
                f"{reservation.starts_at.isoformat()}."
            )
        else:
            description = f"Asset returned: {{asset}} at {scheduled_for.isoformat()}."
        display_name = user.display_name or "ARA user"
        text = f"{description.format(asset=asset.name)}\nReserved by: {display_name}"
        asset_url = (
            (f"{str(self.settings.public_url).rstrip('/')}/assets/{asset.id}")
            .replace("(", "%28")
            .replace(")", "%29")
        )
        asset_link = f"[{escape_markdown(asset.name)}]({asset_url})"
        markdown = (
            f"{description.format(asset=asset_link)}\n\n"
            f"Reserved by: {escape_markdown(display_name)}"
        )
        for destination_type, enabled, destination, reason in (
            ("person", personal, user.email, "missing_email"),
            ("room", room, group.webex_room_id, "missing_room"),
        ):
            if not enabled or await self.deliveries.exists(key, destination_type):
                continue
            if destination_type == "room" and not asset.room_notifications_enabled:
                reason, destination = "asset_room_disabled", None
            self.session.add(
                WebexDelivery(
                    group_id=group.id,
                    asset_id=asset.id,
                    reservation_id=reservation.id,
                    event_key=key,
                    kind=f"end_reminder:{offset}" if kind == "end_reminder" else kind,
                    destination_type=destination_type,
                    destination=destination,
                    text=text,
                    markdown=markdown,
                    scheduled_for=scheduled_for,
                    expected_end=reservation.ends_at
                    if kind == "end_reminder"
                    else None,
                    state="pending" if destination else "skipped",
                    error_code=None if destination else reason,
                    next_attempt_at=utc_now(),
                )
            )

    async def generate_due(self) -> None:
        now = utc_now()
        # SQLite write serialization also protects producer deduplication against
        # transactional request producers. No HTTP call occurs under this lock.
        from sqlalchemy import text

        await self.session.execute(text("BEGIN IMMEDIATE"))
        starts = list(
            await self.session.scalars(
                select(Reservation)
                .where(
                    Reservation.start_notification_processed.is_(False),
                    Reservation.starts_at <= now,
                )
                .order_by(Reservation.starts_at)
                .limit(100)
            )
        )
        for reservation in starts:
            if (
                reservation.status == ReservationStatus.ACTIVE
                and reservation.starts_at >= now - START_CATCH_UP
                and (reservation.ends_at is None or reservation.ends_at > now)
            ):
                await self.enqueue_event(
                    reservation,
                    "start",
                    reservation.starts_at,
                    personal=reservation.personal_start_eligible,
                    room=True,
                )
            reservation.start_notification_processed = True
        if self.settings.webex_bot_token is not None:
            offsets = self.settings.notification_reminder_offsets_minutes
            for offset in offsets:
                already_queued = (
                    select(WebexDelivery.id)
                    .where(
                        WebexDelivery.reservation_id == Reservation.id,
                        WebexDelivery.expected_end == Reservation.ends_at,
                        WebexDelivery.kind == f"end_reminder:{offset}",
                        WebexDelivery.destination_type == "person",
                    )
                    .exists()
                )
                candidates = list(
                    await self.session.scalars(
                        select(Reservation)
                        .where(
                            Reservation.status == ReservationStatus.ACTIVE,
                            Reservation.ends_at
                            >= now - REMINDER_CATCH_UP + timedelta(minutes=offset),
                            Reservation.ends_at <= now + timedelta(minutes=offset),
                            Reservation.starts_at <= now,
                            ~already_queued,
                        )
                        .order_by(Reservation.ends_at)
                        .limit(100)
                    )
                )
                for reservation in candidates:
                    assert reservation.ends_at is not None
                    due = reservation.ends_at - timedelta(minutes=offset)
                    if now - REMINDER_CATCH_UP <= due <= now:
                        await self.enqueue_event(
                            reservation,
                            "end_reminder",
                            due,
                            personal=True,
                            offset=offset,
                        )
        await self.deliveries.cleanup(
            now=now,
            room_cutoff=now - ROOM_DELIVERY_RETENTION,
            personal_cutoff=now - PERSONAL_DELIVERY_RETENTION,
        )
        await self.session.commit()

    async def require_group(self, roles: EffectiveRoles, group_id: uuid.UUID) -> Group:
        AuthorizationService.require_group_admin(roles, group_id)
        group = await self.session.get(Group, group_id)
        if group is None:
            raise DomainError("group_not_found", "Group not found", status_code=404)
        return group

    async def test_room(
        self, roles: EffectiveRoles, group_id: uuid.UUID
    ) -> WebexDelivery:
        group = await self.require_group(roles, group_id)
        if group.archived_at is not None:
            raise DomainError(
                "group_archived",
                "Reactivate the group before sending a test",
                status_code=409,
            )
        if self.settings.webex_bot_token is None:
            raise DomainError(
                "webex_disabled", "Webex bot is not configured", status_code=409
            )
        if not group.webex_room_id:
            raise DomainError(
                "webex_room_missing",
                "Save a Webex room identifier first",
                status_code=409,
            )
        delivery = WebexDelivery(
            group_id=group.id,
            event_key=f"test:{uuid.uuid4()}",
            kind="test",
            destination_type="room",
            destination=group.webex_room_id,
            text=f"ARA test notification for {group.name}. No action required.",
            scheduled_for=utc_now(),
            next_attempt_at=utc_now(),
        )
        self.session.add(delivery)
        await self.session.commit()
        return delivery

    async def invalid_reason(
        self, delivery: WebexDelivery, now: datetime
    ) -> str | None:
        group = await self.session.get(Group, delivery.group_id)
        if group is None or group.archived_at is not None:
            return "group_unavailable"
        if delivery.destination_type == "room":
            if group.webex_room_id != delivery.destination:
                return "room_changed"
            if delivery.asset_id:
                asset = await self.session.get(Asset, delivery.asset_id)
                if asset is None or not asset.room_notifications_enabled:
                    return "asset_room_disabled"
        if delivery.reservation_id and delivery.kind != "return":
            reservation = await self.session.get(Reservation, delivery.reservation_id)
            if reservation is None or reservation.status != ReservationStatus.ACTIVE:
                return "reservation_terminal"
            if (
                delivery.kind.startswith("end_reminder:")
                and reservation.ends_at != delivery.expected_end
            ):
                return "reservation_end_changed"
            if delivery.kind == "start" and (
                now - delivery.scheduled_for > START_CATCH_UP
                or (reservation.ends_at is not None and reservation.ends_at <= now)
            ):
                return "start_expired"
            if (
                delivery.kind.startswith("end_reminder:")
                and now - delivery.scheduled_for > REMINDER_CATCH_UP
            ):
                return "reminder_expired"
        return None

    async def dispatch(self, client: WebexClient) -> int:
        now = utc_now()
        # A persisted global cooldown avoids hammering Webex on token failures
        # and rate limits, including after process restart.
        cooldown = await self.session.scalar(
            select(WebexDelivery.id)
            .where(
                WebexDelivery.error_code.in_(("invalid_bot_token", "rate_limited")),
                WebexDelivery.next_attempt_at > now,
            )
            .limit(1)
        )
        if cooldown is not None:
            await self.session.rollback()
            return 0
        await self.session.execute(
            update(WebexDelivery)
            .where(
                WebexDelivery.state == "sending",
                WebexDelivery.claimed_at < now - timedelta(minutes=5),
            )
            .values(state="pending", claimed_at=None)
        )
        await self.session.commit()
        ids = list(
            await self.session.scalars(
                select(WebexDelivery.id)
                .where(
                    WebexDelivery.state == "pending",
                    WebexDelivery.next_attempt_at <= now,
                )
                .order_by(WebexDelivery.next_attempt_at, WebexDelivery.id)
                .limit(DISPATCH_BATCH)
            )
        )
        await self.session.rollback()
        delivered = 0
        for delivery_id in ids:
            claimed = await self.session.scalar(
                update(WebexDelivery)
                .where(
                    WebexDelivery.id == delivery_id,
                    WebexDelivery.state == "pending",
                )
                .values(state="sending", claimed_at=utc_now())
                .returning(WebexDelivery.id)
            )
            await self.session.commit()
            if claimed is None:
                continue
            delivery = await self.session.get(WebexDelivery, delivery_id)
            assert delivery is not None
            reason = await self.invalid_reason(delivery, utc_now())
            if reason:
                delivery.state, delivery.error_code = "skipped", reason
                await self.session.commit()
                continue
            if delivery.attempts >= MAX_ATTEMPTS:
                delivery.state, delivery.error_code = "failed", "retry_exhausted"
                delivery.claimed_at = None
                await self.session.commit()
                continue
            destination_type, destination, message, markdown = (
                delivery.destination_type,
                delivery.destination,
                delivery.text,
                delivery.markdown,
            )
            assert destination is not None
            # Persist the attempt before sending, then close the read/write
            # transaction while waiting on the network.
            delivery.attempts += 1
            await self.session.commit()
            sent = await client.send(
                destination_type, destination, message, markdown=markdown
            )
            delivery.claimed_at = None
            delivery.error_code = sent.error_code
            if sent.error_code == "rate_limited" and sent.retry_after is not None:
                delivery.next_attempt_at = utc_now() + timedelta(
                    seconds=sent.retry_after
                )
            if sent.error_code is None:
                delivery.state, delivery.delivered_at = "delivered", utc_now()
                delivery.message_id = sent.message_id
                delivered += 1
            elif sent.error_code == "invalid_bot_token":
                delivery.state = "failed"
                delivery.next_attempt_at = utc_now() + timedelta(minutes=15)
            elif sent.retry_after is not None and delivery.attempts < MAX_ATTEMPTS:
                delivery.state = "pending"
                delay = max(
                    sent.retry_after, min(30 * 2 ** (delivery.attempts - 1), 3600)
                )
                delivery.next_attempt_at = utc_now() + timedelta(seconds=delay)
            else:
                delivery.state = "failed"
            await self.session.commit()
            if sent.error_code in ("invalid_bot_token", "rate_limited"):
                break
        return delivered
