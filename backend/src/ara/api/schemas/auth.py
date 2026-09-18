"""Authentication response schemas."""

from pydantic import BaseModel


class SessionUserSchema(BaseModel):
    id: str
    display_name: str | None
    email: str | None


class SessionSchema(BaseModel):
    authenticated: bool
    user: SessionUserSchema | None = None
