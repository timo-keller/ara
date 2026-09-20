"""HTTP schemas for querying append-only audit history."""

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, model_validator

from ara.services.audit import AuditAction, AuditTargetType


class AuditQuerySchema(BaseModel):
    """Optional filters and pagination for reverse-chronological audit history."""

    model_config = ConfigDict(extra="forbid")

    group_id: uuid.UUID | None = None
    actor_id: str | None = None
    action: list[AuditAction] | None = None
    target_type: list[AuditTargetType] | None = None
    target_id: str | None = None
    created_at_from: datetime | None = None
    created_at_to: datetime | None = None
    offset: int = 0
    limit: int = 50

    @model_validator(mode="after")
    def requires_utc_ordered_time_range(self) -> AuditQuerySchema:
        for name, value in (
            ("created_at_from", self.created_at_from),
            ("created_at_to", self.created_at_to),
        ):
            if value is not None and (
                value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value)
            ):
                raise ValueError(f"{name} must be timezone-aware UTC")
        if (
            self.created_at_from is not None
            and self.created_at_to is not None
            and self.created_at_from > self.created_at_to
        ):
            raise ValueError("created_at_from must be before or equal to created_at_to")
        return self


class AuditEventSchema(BaseModel):
    """A safe API representation of one persisted audit event."""

    id: uuid.UUID
    actor_id: uuid.UUID | None
    actor_name: str | None = None
    group_id: uuid.UUID | None
    action: str
    target_type: str
    target_id: str
    target_name: str | None = None
    before_state: dict[str, Any] | None
    after_state: dict[str, Any] | None
    correlation_id: str | None
    created_at: datetime


class AuditEventListSchema(BaseModel):
    items: list[AuditEventSchema]
    total: int
    offset: int
    limit: int
