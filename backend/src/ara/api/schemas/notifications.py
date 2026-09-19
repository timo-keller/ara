"""HTTP schemas for current-user notifications."""

import uuid
from datetime import datetime

from pydantic import BaseModel


class NotificationSchema(BaseModel):
    id: uuid.UUID
    reservation_id: uuid.UUID | None
    kind: str
    title: str
    body: str | None
    scheduled_for: datetime | None
    created_at: datetime
    read_at: datetime | None


class NotificationListSchema(BaseModel):
    items: list[NotificationSchema]
    total: int
    offset: int
    limit: int
