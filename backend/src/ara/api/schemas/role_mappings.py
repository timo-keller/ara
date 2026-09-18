"""HTTP schemas for OIDC claim role mapping administration."""

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints, model_validator

from ara.domain.models import GroupRole

Expression = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Priority = Annotated[int, Field(ge=0)]


class RoleMappingCreateSchema(BaseModel):
    group_id: uuid.UUID
    expression: Expression
    role: GroupRole
    enabled: bool = True
    priority: Priority = 0


class RoleMappingUpdateSchema(BaseModel):
    group_id: uuid.UUID | None = None
    expression: Expression | None = None
    role: GroupRole | None = None
    enabled: bool | None = None
    priority: Priority | None = None

    @model_validator(mode="after")
    def requires_change(self) -> RoleMappingUpdateSchema:
        if not self.model_fields_set:
            raise ValueError("At least one role mapping field is required")
        return self


class RoleMappingTestSchema(BaseModel):
    expression: Expression


class RoleMappingSchema(BaseModel):
    id: uuid.UUID
    group_id: uuid.UUID
    expression: str
    role: GroupRole
    enabled: bool
    priority: int
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None


class RoleMappingListSchema(BaseModel):
    items: list[RoleMappingSchema]
    total: int
    offset: int
    limit: int


class RoleMappingTestResultSchema(BaseModel):
    matches: bool
