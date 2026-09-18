"""HTTP schemas for the group-scoped asset catalogue."""

import uuid
from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, StringConstraints, model_validator

AssetName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
]
AssetType = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
]

_CREDENTIAL_KEY_PARTS = (
    "password",
    "passwd",
    "credential",
    "secret",
    "token",
    "private_key",
    "api_key",
    "access_key",
)


def _reject_credentials(value: object) -> object:
    """Reject credential-like metadata before it reaches persistence."""
    if isinstance(value, dict):
        for key, nested_value in value.items():
            normalized_key = str(key).lower().replace("-", "_")
            if any(part in normalized_key for part in _CREDENTIAL_KEY_PARTS):
                raise ValueError("Credential-like fields are not accepted")
            _reject_credentials(nested_value)
    elif isinstance(value, list):
        for nested_value in value:
            _reject_credentials(nested_value)
    return value


class _AssetInputSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def rejects_credential_metadata(self) -> _AssetInputSchema:
        _reject_credentials(getattr(self, "operational_metadata", None))
        return self


class AssetCreateSchema(_AssetInputSchema):
    group_id: uuid.UUID
    asset_type: AssetType
    name: AssetName
    description: str | None = None
    operational_metadata: dict[str, Any] | None = None
    remote_host: str | None = None
    remote_url: str | None = None
    operating_system: str | None = None
    access_instructions: str | None = None
    webex_room_id: str | None = None


class AssetUpdateSchema(_AssetInputSchema):
    asset_type: AssetType | None = None
    name: AssetName | None = None
    description: str | None = None
    operational_metadata: dict[str, Any] | None = None
    remote_host: str | None = None
    remote_url: str | None = None
    operating_system: str | None = None
    access_instructions: str | None = None
    webex_room_id: str | None = None

    @model_validator(mode="after")
    def requires_change(self) -> AssetUpdateSchema:
        if not self.model_fields_set:
            raise ValueError("At least one asset field is required")
        return self


class AssetSchema(BaseModel):
    id: uuid.UUID
    group_id: uuid.UUID
    asset_type: str
    name: str
    description: str | None
    operational_metadata: dict[str, Any] | None
    remote_host: str | None
    remote_url: str | None
    operating_system: str | None
    access_instructions: str | None
    webex_room_id: str | None
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None


class AssetListSchema(BaseModel):
    items: list[AssetSchema]
    total: int
    offset: int
    limit: int
