"""HTTP transport endpoints for group administration."""

import uuid
from typing import Annotated

from fastapi import Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from ara.api.routers import api_router
from ara.api.routers.auth import (
    get_current_application_session,
    require_csrf,
)
from ara.api.schemas.groups import (
    GroupCreateSchema,
    GroupListSchema,
    GroupSchema,
    GroupUpdateSchema,
    WebexConfigurationSchema,
    WebexDeliverySchema,
    WebexStatusSchema,
)
from ara.core.config import Settings, get_settings
from ara.core.request_context import get_correlation_id
from ara.domain.models import ApplicationSession
from ara.infrastructure.database import get_session
from ara.services.audit import AuditContext
from ara.services.authorization import EffectiveRoles, RoleResolutionService
from ara.services.groups import GroupService
from ara.services.webex import WebexService


async def get_effective_roles(
    application_session: Annotated[
        ApplicationSession, Depends(get_current_application_session)
    ],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> EffectiveRoles:
    """Resolve the authenticated user's current, server-side effective roles."""
    return await RoleResolutionService(
        session,
        get_settings().owner_subjects.get_secret_value(),
        get_settings().owner_claim_expression,
    ).resolve_session(application_session)


async def get_audit_context(
    roles: Annotated[EffectiveRoles, Depends(get_effective_roles)],
) -> AuditContext:
    """Build transport-neutral audit metadata from authenticated role resolution."""
    return AuditContext(actor_id=roles.actor_id, correlation_id=get_correlation_id())


def _group_schema(group: object) -> GroupSchema:
    return GroupSchema.model_validate(group, from_attributes=True)


@api_router.post(
    "/groups", response_model=GroupSchema, status_code=status.HTTP_201_CREATED
)
async def create_group(
    payload: GroupCreateSchema,
    roles: Annotated[EffectiveRoles, Depends(get_effective_roles)],
    _csrf: Annotated[None, Depends(require_csrf)],
    audit: Annotated[AuditContext, Depends(get_audit_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> GroupSchema:
    group = await GroupService(session, audit).create(roles, **payload.model_dump())
    return _group_schema(group)


@api_router.get("/groups", response_model=GroupListSchema)
async def list_groups(
    roles: Annotated[EffectiveRoles, Depends(get_effective_roles)],
    session: Annotated[AsyncSession, Depends(get_session)],
    archived: Annotated[bool | None, Query()] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> GroupListSchema:
    groups, total = await GroupService(session).list_groups(
        roles, archived=archived, offset=offset, limit=limit
    )
    return GroupListSchema(
        items=[_group_schema(group) for group in groups],
        total=total,
        offset=offset,
        limit=limit,
    )


@api_router.get("/groups/{group_id}", response_model=GroupSchema)
async def get_group(
    group_id: uuid.UUID,
    roles: Annotated[EffectiveRoles, Depends(get_effective_roles)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> GroupSchema:
    return _group_schema(await GroupService(session).get(roles, group_id))


@api_router.patch("/groups/{group_id}", response_model=GroupSchema)
async def update_group(
    group_id: uuid.UUID,
    payload: GroupUpdateSchema,
    roles: Annotated[EffectiveRoles, Depends(get_effective_roles)],
    _csrf: Annotated[None, Depends(require_csrf)],
    audit: Annotated[AuditContext, Depends(get_audit_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> GroupSchema:
    values = payload.model_dump(exclude_unset=True)
    group = await GroupService(session, audit).update(
        roles,
        group_id,
        name=values.get("name"),
        description=values.get("description"),
        update_name="name" in values,
        update_description="description" in values,
    )
    return _group_schema(group)


@api_router.post("/groups/{group_id}/archive", response_model=GroupSchema)
async def archive_group(
    group_id: uuid.UUID,
    roles: Annotated[EffectiveRoles, Depends(get_effective_roles)],
    _csrf: Annotated[None, Depends(require_csrf)],
    audit: Annotated[AuditContext, Depends(get_audit_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> GroupSchema:
    return _group_schema(await GroupService(session, audit).archive(roles, group_id))


@api_router.post("/groups/{group_id}/reactivate", response_model=GroupSchema)
async def reactivate_group(
    group_id: uuid.UUID,
    roles: Annotated[EffectiveRoles, Depends(get_effective_roles)],
    _csrf: Annotated[None, Depends(require_csrf)],
    audit: Annotated[AuditContext, Depends(get_audit_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> GroupSchema:
    return _group_schema(await GroupService(session, audit).reactivate(roles, group_id))


@api_router.patch("/groups/{group_id}/webex", response_model=GroupSchema)
async def update_webex_room(
    group_id: uuid.UUID,
    payload: WebexConfigurationSchema,
    roles: Annotated[EffectiveRoles, Depends(get_effective_roles)],
    _csrf: Annotated[None, Depends(require_csrf)],
    audit: Annotated[AuditContext, Depends(get_audit_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> GroupSchema:
    return _group_schema(
        await GroupService(session, audit).update_webex(
            roles,
            group_id,
            payload.webex_room_id,
            space_link=payload.webex_space_link,
            resolve_link="webex_space_link" in payload.model_fields_set,
            settings=settings,
        )
    )


@api_router.get("/groups/{group_id}/webex", response_model=WebexStatusSchema)
async def webex_status(
    group_id: uuid.UUID,
    roles: Annotated[EffectiveRoles, Depends(get_effective_roles)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> WebexStatusSchema:
    service = WebexService(session, settings)
    await service.require_group(roles, group_id)
    items, counts = await service.deliveries.room_status(group_id)
    return WebexStatusSchema(
        configured=service.settings.webex_bot_token is not None,
        counts=counts,
        items=[
            WebexDeliverySchema.model_validate(item, from_attributes=True)
            for item in items
        ],
    )


@api_router.post(
    "/groups/{group_id}/webex/test", response_model=WebexDeliverySchema, status_code=202
)
async def test_webex_room(
    group_id: uuid.UUID,
    roles: Annotated[EffectiveRoles, Depends(get_effective_roles)],
    _csrf: Annotated[None, Depends(require_csrf)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> WebexDeliverySchema:
    delivery = await WebexService(session, settings).test_room(roles, group_id)
    return WebexDeliverySchema.model_validate(delivery, from_attributes=True)
