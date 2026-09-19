"""HTTP transport endpoints for Owner-managed OIDC role mappings."""

import uuid
from typing import Annotated

from fastapi import Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from ara.api.routers import api_router
from ara.api.routers.auth import get_current_application_session, require_csrf
from ara.api.routers.groups import get_audit_context, get_effective_roles
from ara.api.schemas.role_mappings import (
    RoleMappingCreateSchema,
    RoleMappingListSchema,
    RoleMappingSchema,
    RoleMappingTestResultSchema,
    RoleMappingTestSchema,
    RoleMappingUpdateSchema,
)
from ara.domain.models import ApplicationSession
from ara.infrastructure.database import get_session
from ara.services.audit import AuditContext
from ara.services.authorization import EffectiveRoles
from ara.services.role_mappings import RoleMappingService


def _mapping_schema(mapping: object) -> RoleMappingSchema:
    return RoleMappingSchema.model_validate(mapping, from_attributes=True)


@api_router.post(
    "/role-mappings",
    response_model=RoleMappingSchema,
    status_code=status.HTTP_201_CREATED,
)
async def create_role_mapping(
    payload: RoleMappingCreateSchema,
    roles: Annotated[EffectiveRoles, Depends(get_effective_roles)],
    _csrf: Annotated[None, Depends(require_csrf)],
    audit: Annotated[AuditContext, Depends(get_audit_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> RoleMappingSchema:
    return _mapping_schema(
        await RoleMappingService(session, audit).create(roles, **payload.model_dump())
    )


@api_router.get("/role-mappings", response_model=RoleMappingListSchema)
async def list_role_mappings(
    roles: Annotated[EffectiveRoles, Depends(get_effective_roles)],
    session: Annotated[AsyncSession, Depends(get_session)],
    archived: Annotated[bool | None, Query()] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> RoleMappingListSchema:
    mappings, total = await RoleMappingService(session).list_mappings(
        roles, archived=archived, offset=offset, limit=limit
    )
    return RoleMappingListSchema(
        items=[_mapping_schema(mapping) for mapping in mappings],
        total=total,
        offset=offset,
        limit=limit,
    )


@api_router.patch("/role-mappings/{mapping_id}", response_model=RoleMappingSchema)
async def update_role_mapping(
    mapping_id: uuid.UUID,
    payload: RoleMappingUpdateSchema,
    roles: Annotated[EffectiveRoles, Depends(get_effective_roles)],
    _csrf: Annotated[None, Depends(require_csrf)],
    audit: Annotated[AuditContext, Depends(get_audit_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> RoleMappingSchema:
    values = payload.model_dump(exclude_unset=True)
    return _mapping_schema(
        await RoleMappingService(session, audit).update(
            roles,
            mapping_id,
            group_id=values.get("group_id"),
            expression=values.get("expression"),
            role=values.get("role"),
            enabled=values.get("enabled"),
            priority=values.get("priority"),
        )
    )


@api_router.post(
    "/role-mappings/{mapping_id}/disable", response_model=RoleMappingSchema
)
async def disable_role_mapping(
    mapping_id: uuid.UUID,
    roles: Annotated[EffectiveRoles, Depends(get_effective_roles)],
    _csrf: Annotated[None, Depends(require_csrf)],
    audit: Annotated[AuditContext, Depends(get_audit_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> RoleMappingSchema:
    return _mapping_schema(
        await RoleMappingService(session, audit).disable(roles, mapping_id)
    )


@api_router.post(
    "/role-mappings/{mapping_id}/archive", response_model=RoleMappingSchema
)
async def archive_role_mapping(
    mapping_id: uuid.UUID,
    roles: Annotated[EffectiveRoles, Depends(get_effective_roles)],
    _csrf: Annotated[None, Depends(require_csrf)],
    audit: Annotated[AuditContext, Depends(get_audit_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> RoleMappingSchema:
    return _mapping_schema(
        await RoleMappingService(session, audit).archive(roles, mapping_id)
    )


@api_router.post("/role-mappings/test", response_model=RoleMappingTestResultSchema)
async def test_role_mapping_expression(
    payload: RoleMappingTestSchema,
    application_session: Annotated[
        ApplicationSession, Depends(get_current_application_session)
    ],
    roles: Annotated[EffectiveRoles, Depends(get_effective_roles)],
    _csrf: Annotated[None, Depends(require_csrf)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> RoleMappingTestResultSchema:
    matches = await RoleMappingService(session).test_expression(
        roles, expression=payload.expression, claims=application_session.oidc_claims
    )
    return RoleMappingTestResultSchema(matches=matches)
