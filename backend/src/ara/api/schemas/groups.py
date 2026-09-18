"""HTTP schemas for group administration."""

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, StringConstraints, model_validator

GroupName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
]


class GroupCreateSchema(BaseModel):
    name: GroupName
    description: str | None = None


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
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None


class GroupListSchema(BaseModel):
    items: list[GroupSchema]
    total: int
    offset: int
    limit: int
