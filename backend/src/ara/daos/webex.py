"""Bounded outbox queries. Services own commits and authorization."""

import uuid
from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ara.domain.models import WebexDelivery


class WebexDAO:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def exists(self, event_key: str, destination_type: str) -> bool:
        return (
            await self.session.scalar(
                select(WebexDelivery.id).where(
                    WebexDelivery.event_key == event_key,
                    WebexDelivery.destination_type == destination_type,
                )
            )
            is not None
        )

    async def room_status(
        self, group_id: uuid.UUID
    ) -> tuple[list[WebexDelivery], dict[str, int]]:
        scope = (
            WebexDelivery.group_id == group_id,
            WebexDelivery.destination_type == "room",
        )
        items = list(
            await self.session.scalars(
                select(WebexDelivery)
                .where(*scope)
                .order_by(WebexDelivery.created_at.desc(), WebexDelivery.id.desc())
                .limit(20)
            )
        )
        rows = (
            await self.session.execute(
                select(WebexDelivery.state, func.count())
                .where(*scope)
                .group_by(WebexDelivery.state)
            )
        ).all()
        counts = {state: count for state, count in rows}
        return items, counts

    async def cleanup(self, cutoff: datetime) -> None:
        ids = (
            select(WebexDelivery.id)
            .where(
                WebexDelivery.state.in_(("delivered", "failed", "skipped")),
                WebexDelivery.created_at < cutoff,
            )
            .limit(100)
        )
        await self.session.execute(
            delete(WebexDelivery).where(WebexDelivery.id.in_(ids))
        )
