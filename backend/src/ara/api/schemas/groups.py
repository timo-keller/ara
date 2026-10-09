"""HTTP schemas for group administration."""

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, StringConstraints, field_validator, model_validator

GroupName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
]


class WebexRoomSchema(BaseModel):
    webex_room_id: (
        Annotated[str, StringConstraints(strip_whitespace=True, max_length=255)] | None
    ) = None

    @field_validator("webex_room_id")
    @classmethod
    def normalize_room(cls, value: str | None) -> str | None:
        if not value:
            return None
        if any(character.isspace() for character in value):
            raise ValueError("Room identifiers cannot contain whitespace")
        return value


class GroupCreateSchema(WebexRoomSchema):
    name: GroupName
    description: str | None = None


class WebexConfigurationSchema(WebexRoomSchema):
    webex_space_link: (
        Annotated[str, StringConstraints(strip_whitespace=True, max_length=255)] | None
    ) = None

    @model_validator(mode="after")
    def requires_one_setting(self) -> WebexConfigurationSchema:
        if self.model_fields_set not in ({"webex_room_id"}, {"webex_space_link"}):
            raise ValueError(
                "Supply exactly one Webex space link or legacy room identifier"
            )
        return self


class GroupUpdateSchema(BaseModel):
    name: GroupName | None = None
    description: str | None = None

    @model_validator(mode="after")
    def requires_change(self) -> GroupUpdateSchema:
        if not self.model_fields_set:
            raise ValueError("At least one group field is required")
        return self


class GroupSchema(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    webex_room_id: str | None
    webex_space_link: str | None
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None


class GroupListSchema(BaseModel):
    items: list[GroupSchema]
    total: int
    offset: int
    limit: int


class WebexDeliverySchema(BaseModel):
    id: uuid.UUID
    kind: str
    state: str
    attempts: int
    scheduled_for: datetime
    created_at: datetime
    delivered_at: datetime | None
    error_code: str | None


class WebexStatusSchema(BaseModel):
    configured: bool
    counts: dict[str, int]
    items: list[WebexDeliverySchema]
