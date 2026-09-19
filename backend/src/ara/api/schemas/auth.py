"""Authentication response schemas."""

from pydantic import BaseModel


class SessionUserSchema(BaseModel):
    id: str
    display_name: str | None
    email: str | None


class EffectiveRolesSchema(BaseModel):
    """Roles resolved by the server from the live session's retained claims."""

    is_owner: bool
    group_roles: dict[str, str]


class SessionSchema(BaseModel):
    authenticated: bool
    user: SessionUserSchema | None = None
    roles: EffectiveRolesSchema | None = None


class LogoutSchema(BaseModel):
    """The optional, server-selected identity-provider logout destination."""

    provider_logout_url: str | None = None
