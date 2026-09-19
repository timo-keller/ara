"""HTTP transport endpoints for current-user notifications."""

import uuid
from typing import Annotated

from fastapi import Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ara.api.routers import api_router
from ara.api.routers.auth import require_authenticated_user, require_csrf
from ara.api.schemas.notifications import NotificationListSchema, NotificationSchema
from ara.domain.models import Notification, User
from ara.infrastructure.database import get_session
from ara.services.notifications import NotificationService


def _notification_schema(notification: Notification) -> NotificationSchema:
    return NotificationSchema.model_validate(notification, from_attributes=True)


@api_router.get("/notifications", response_model=NotificationListSchema)
async def list_notifications(
    user: Annotated[User, Depends(require_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> NotificationListSchema:
    notifications, total = await NotificationService(session).list_own(
        user_id=user.id, offset=offset, limit=limit
    )
    return NotificationListSchema(
        items=[_notification_schema(notification) for notification in notifications],
        total=total,
        offset=offset,
        limit=limit,
    )


@api_router.post(
    "/notifications/{notification_id}/read", response_model=NotificationSchema
)
async def mark_notification_read(
    notification_id: uuid.UUID,
    user: Annotated[User, Depends(require_authenticated_user)],
    _csrf: Annotated[None, Depends(require_csrf)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> NotificationSchema:
    notification = await NotificationService(session).mark_read(
        user_id=user.id, notification_id=notification_id
    )
    return _notification_schema(notification)


@api_router.post("/notifications/read", status_code=204)
async def mark_all_notifications_read(
    user: Annotated[User, Depends(require_authenticated_user)],
    _csrf: Annotated[None, Depends(require_csrf)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    await NotificationService(session).mark_all_read(user_id=user.id)
