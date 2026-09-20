"""HTTP schemas for reservation creation and inspection."""

import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, model_validator

from ara.domain.models import ReservationStatus


class ReservationCreateSchema(BaseModel):
    """A requested exclusive reservation interval."""

    model_config = ConfigDict(extra="forbid")

    asset_id: uuid.UUID
    starts_at: datetime
    ends_at: datetime | None = None

    @model_validator(mode="after")
    def requires_utc_positive_interval(self) -> ReservationCreateSchema:
        for name, value in (("starts_at", self.starts_at), ("ends_at", self.ends_at)):
            if value is not None and (
                value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value)
            ):
                raise ValueError(f"{name} must be timezone-aware UTC")
        if self.ends_at is not None and self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be after starts_at")
        return self


class ReservationExtensionSchema(BaseModel):
    """A later end time for a bounded reservation."""

    model_config = ConfigDict(extra="forbid")

    ends_at: datetime

    @model_validator(mode="after")
    def requires_utc_end(self) -> ReservationExtensionSchema:
        if self.ends_at.tzinfo is None or self.ends_at.utcoffset() != UTC.utcoffset(
            self.ends_at
        ):
            raise ValueError("ends_at must be timezone-aware UTC")
        return self


class ReservationSchema(BaseModel):
    id: uuid.UUID
    asset_id: uuid.UUID
    asset_name: str | None = None
    user_id: uuid.UUID
    starts_at: datetime
    ends_at: datetime | None
    status: ReservationStatus
    created_at: datetime
    updated_at: datetime
    returned_at: datetime | None
    cancelled_at: datetime | None
    ended_at: datetime | None


class ReservationListSchema(BaseModel):
    items: list[ReservationSchema]
    total: int
    offset: int
    limit: int
